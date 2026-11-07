"""BackupEngine: backup, verify, restore, retention. No Qt here; the UI runs these in worker threads."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from safepoint.config import default_settings
from safepoint.db.database import Database
from safepoint.util import human_size, parse_iso, utcnow_iso

from .core import build_manifest, hash_file, parse_retention, scan_folder, select_to_keep
from .errors import Cancelled, HashMismatch, SafeFileError, SourceChanged, StoreError
from .stores import build_stores, store_from_id, validate_destination


def _noop(*_args, **_kwargs):
    pass


@dataclass
class BackupResult:
    status: str                    # verified | failed | pending | unchanged
    snapshot_id: str | None = None
    files: int = 0
    total_bytes: int = 0
    uploaded_bytes: int = 0
    added: int = 0
    modified: int = 0
    removed: int = 0
    skipped: list = field(default_factory=list)
    destinations: list = field(default_factory=list)
    message: str = ""


@dataclass
class VerifyResult:
    state: str                     # verified | failed | pending
    problems: list = field(default_factory=list)
    unreachable: list = field(default_factory=list)


@dataclass
class RestoreResult:
    restored: int = 0
    skipped_existing: int = 0
    failed: list = field(default_factory=list)   # [(path, reason)]
    bytes_written: int = 0
    destination: str = ""


def _diff(prev_map, files):
    cur = {f.path: f for f in files}
    added = [p for p in cur if p not in prev_map]
    removed = [p for p in prev_map if p not in cur]
    modified = [p for p in cur if p in prev_map and prev_map[p]["sha256"] != cur[p].sha256]
    return added, modified, removed


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def safe_join(dest: Path, rel: str) -> Path:
    parts = [p for p in rel.split("/") if p]
    if not parts or any(p in (".", "..") or ":" in p or p.startswith("\\") for p in parts):
        raise SafeFileError(f"Unsafe path in version record: {rel}")
    target = dest.joinpath(*parts)
    base = os.path.normcase(os.path.abspath(dest))
    if not os.path.normcase(os.path.abspath(target)).startswith(base + os.sep):
        raise SafeFileError(f"Unsafe path in version record: {rel}")
    return target


class BackupEngine:
    def __init__(self, db: Database):
        self.db = db

    def settings(self) -> dict:
        return self.db.all_settings(default_settings())

    # ================================================================ backup
    def backup(self, project_id, kind="Manual", progress=None, cancel=None, force=False, note="") -> BackupResult:
        """`force=True` always records a new version, even if nothing changed (used by quick saves)."""
        progress = progress or _noop
        project = self.db.get_project(project_id)
        if not project:
            raise SafeFileError("That project no longer exists.")
        self.db.purge_incomplete()
        self.db.touch_attempt(project_id)
        try:
            return self._backup(project, kind, progress, cancel, force, note)
        except Cancelled:
            raise
        except Exception as err:
            message = str(err) or type(err).__name__
            self.db.set_project_error(project_id, message)
            self.db.log("error", "Backup", f"Backup failed for {project['name']}", message)
            if isinstance(err, SafeFileError):
                raise
            raise SafeFileError(message) from err

    def _backup(self, p, kind, progress, cancel, force=False, user_note="") -> BackupResult:
        db, root = self.db, p["path"]
        if p["kind"] == "project" and not os.path.isdir(root):
            raise SafeFileError(f"The folder {root} was not found.")
        if not os.path.exists(root):
            raise SafeFileError(f"{root} was not found.")
        stores = build_stores(self.settings(), p["destination"])
        for s in stores:
            progress("Checking destination", 0, 0, s.label)
            s.check()
            validate_destination(root, s)

        progress("Scanning folder", 0, 0, root)
        entries, skipped = scan_folder(root, json.loads(p["exclusions"]), cancel,
                                       on_count=lambda n: progress("Scanning folder", 0, 0, f"{n} files found"))
        prev = db.latest_snapshot(p["id"])
        prev_map = db.snapshot_file_map(prev["seq"]) if prev else {}

        # ---- read and hash (unchanged files reuse the previous hash)
        files, total, tick = [], len(entries), [0.0]
        for i, e in enumerate(entries):
            _check_cancel(cancel)
            progress("Reading files", i, total, e.path)
            cached = prev_map.get(e.path)
            if cached and cached["size"] == e.size and cached["mtime_ns"] == e.mtime_ns:
                e.sha256 = cached["sha256"]
            else:
                def on_bytes(done, e=e, i=i):
                    now = time.monotonic()
                    if now - tick[0] > 0.3:
                        tick[0] = now
                        progress("Reading files", i, total, f"{e.path} ({human_size(done)} of {human_size(e.size)})")
                try:
                    e.sha256, e.size = hash_file(e.abs_path, on_bytes, cancel)
                except OSError as err:
                    skipped.append((e.path, err.strerror or str(err)))
                    continue
            files.append(e)

        added, modified, removed = _diff(prev_map, files)
        if (prev and not force and prev["state"] in ("verified", "pending")
                and not (added or modified or removed)):
            if prev["state"] == "verified":
                db.mark_ok(p["id"])
            db.log("info", "Backup", f"{p['name']}: no changes since {prev['id']}")
            return BackupResult("unchanged", prev["id"], len(files), sum(f.size for f in files),
                                skipped=skipped, destinations=[s.label for s in stores],
                                message="No changes since the last backup.")

        # ---- upload missing content to every destination
        by_sha: dict = {}
        for f in files:
            by_sha.setdefault(f.sha256, []).append(f)
        dropped, uploaded = set(), 0
        for store in stores:
            shas = list(by_sha)
            have = store.has_blobs(shas)
            todo = [s for s in shas if s not in have]
            total_b, done_b = sum(by_sha[s][0].size for s in todo), 0
            for s in todo:
                _check_cancel(cancel)
                candidates = by_sha[s]
                progress(f"Uploading to {store.label}", done_b, total_b, candidates[0].path)
                stored = False
                while candidates:
                    f = candidates[0]
                    try:
                        store.put_blob(s, f.abs_path, f.size)
                        stored = True
                        break
                    except SourceChanged as err:
                        skipped.append((f.path, f"changed or unreadable during backup ({err})"))
                        dropped.add(f.path)
                        candidates.pop(0)
                if stored:
                    done_b += by_sha[s][0].size
                    uploaded += by_sha[s][0].size
                else:
                    by_sha.pop(s, None)
        files = [f for f in files if f.path not in dropped]
        added, modified, removed = _diff(prev_map, files)

        # ---- record the version
        _check_cancel(cancel)
        seq, sid = db.begin_snapshot(p["id"], kind, [s.id for s in stores])
        try:
            created = utcnow_iso()
            manifest = build_manifest(sid, p["name"], created, files, skipped)
            for store in stores:
                progress(f"Saving version to {store.label}", 0, 0, sid)
                store.put_named(f"snapshots/{sid}.json", manifest)
            parts = []
            if user_note.strip():
                parts.append(user_note.strip())
            if prev and not (added or modified or removed):
                parts.append("Same content as the previous version")
            if skipped:
                names = ", ".join(x[0] for x in skipped[:3])
                parts.append(f"{len(skipped)} file(s) skipped: {names}{'…' if len(skipped) > 3 else ''}")
            note = " · ".join(parts)
            db.finish_snapshot(seq, [(f.path, f.sha256, f.size, f.mtime_ns) for f in files],
                               len(added), len(modified), len(removed), len(skipped), note)
        except BaseException:
            db.abort_snapshot(seq)
            raise

        result = BackupResult("pending", sid, len(files), sum(f.size for f in files), uploaded,
                              len(added), len(modified), len(removed), skipped, [s.label for s in stores])
        # ---- verify before claiming success
        try:
            v = self.verify(sid, progress, cancel)
        except StoreError as err:
            result.message = f"Saved, but could not be verified yet: {err}"
            db.log("warning", "Verification", f"{p['name']}: {sid} saved but not verified", str(err))
            return result
        result.status = v.state
        if v.state == "verified":
            db.mark_ok(p["id"])
            result.message = "Backup saved and verified."
            db.log("success", "Backup", f"{p['name']}: {sid} saved and verified",
                   f"{len(files)} files, {human_size(result.total_bytes)}")
            try:
                if p["kind"] == "project":  # quick-save versions are kept until you remove them
                    self.apply_retention(p["id"])
            except Exception as err:  # retention problems must never hide a good backup
                db.log("warning", "Retention", f"Cleanup skipped for {p['name']}", str(err))
        elif v.state == "failed":
            result.message = "Backup saved, but verification failed: " + "; ".join(v.problems)
        else:
            result.message = "Saved, but not every destination could be verified: " + "; ".join(v.unreachable)
        return result

    def quick_save(self, path, destination, note="", progress=None, cancel=None) -> BackupResult:
        """Save a dropped file or folder as a new version in its own history (created on first use)."""
        path = os.path.normpath(path)
        if not os.path.exists(path):
            raise SafeFileError(f"{path} was not found.")
        item = self.db.find_quick_item(path)
        if item is None:
            patterns = self.settings()["default_exclusions"] if os.path.isdir(path) else []
            name = os.path.basename(path.rstrip("\\/")) or path
            item_id = self.db.add_project(name, path, destination, "Manual only", patterns, kind="quick")
        else:
            item_id = item["id"]
            if item["destination"] != destination:
                self.db.update_project(item_id, destination=destination)
        return self.backup(item_id, "Quick save", progress, cancel, force=True, note=note)

    # ================================================================ verify
    def verify(self, snapshot_id, progress=None, cancel=None) -> VerifyResult:
        progress = progress or _noop
        db = self.db
        snap = db.get_snapshot(snapshot_id)
        if not snap:
            raise SafeFileError("That version no longer exists.")
        files = db.snapshot_files(snap["seq"])
        expected = {f["path"]: f["sha256"] for f in files}
        shas = sorted(set(expected.values()))
        paths_by_sha: dict = {}
        for f in files:
            paths_by_sha.setdefault(f["sha256"], []).append(f["path"])
        settings = self.settings()
        problems, unreachable, checked = [], [], 0
        for store_id in json.loads(snap["destinations"]):
            _check_cancel(cancel)
            try:
                store = store_from_id(store_id, settings)
                store.check()
            except StoreError as err:
                unreachable.append(str(err))
                continue
            label = store.label
            progress(f"Verifying on {label}", 0, len(shas), "")
            raw = store.get_named(f"snapshots/{snap['id']}.json")
            if raw is None:
                problems.append(f"{label}: version record is missing")
            else:
                try:
                    recorded = {f["path"]: f["sha256"] for f in json.loads(raw.decode("utf-8"))["files"]}
                except (ValueError, KeyError):
                    recorded = None
                if recorded != expected:
                    problems.append(f"{label}: version record does not match")
            bad, missing = store.verify_blobs(
                shas, on_progress=lambda d, t, label=label: progress(f"Verifying on {label}", d, t, ""), cancel=cancel)
            if bad:
                names = ", ".join(paths_by_sha[s][0] for s in bad[:3])
                problems.append(f"{label}: {len(bad)} damaged item(s), e.g. {names}")
            if missing:
                names = ", ".join(paths_by_sha[s][0] for s in missing[:3])
                problems.append(f"{label}: {len(missing)} missing item(s), e.g. {names}")
            checked += 1
        if problems:
            db.set_snapshot_state(snap["seq"], "failed", "; ".join(problems))
            db.log("error", "Verification", f"Verification failed for {snap['id']} ({snap['project_name']})",
                   "; ".join(problems))
            return VerifyResult("failed", problems, unreachable)
        if unreachable:
            if checked == 0:
                raise StoreError("; ".join(unreachable))
            return VerifyResult("pending", [], unreachable)
        db.set_snapshot_state(snap["seq"], "verified", "")
        db.log("success", "Verification", f"Verification passed for {snap['id']} ({snap['project_name']})")
        if snap["project_id"]:
            latest = db.latest_snapshot(snap["project_id"])
            if latest and latest["seq"] == snap["seq"]:
                db.mark_ok(snap["project_id"])
        return VerifyResult("verified")

    # ================================================================ restore
    def restore(self, snapshot_id, rel_paths, dest_dir, conflict="keep_both",
                progress=None, cancel=None) -> RestoreResult:
        progress = progress or _noop
        db = self.db
        snap = db.get_snapshot(snapshot_id)
        if not snap:
            raise SafeFileError("That version no longer exists.")
        by_path = {f["path"]: f for f in db.snapshot_files(snap["seq"])}
        wanted = [by_path[p] for p in rel_paths if p in by_path]
        settings = self.settings()
        ready, errors = [], []
        for store_id in json.loads(snap["destinations"]):
            try:
                s = store_from_id(store_id, settings)
                s.check()
                ready.append(s)
            except StoreError as err:
                errors.append(str(err))
        if not ready:
            raise StoreError("No backup destination is available for this version. " + " ".join(errors))
        ready.sort(key=lambda s: 0 if s.kind == "local" else 1)  # local first, cloud as fallback

        dest = Path(dest_dir)
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise SafeFileError(f"Cannot create {dest}: {err.strerror or err}") from err
        result = RestoreResult(destination=str(dest))
        total_b, done_b = sum(f["size"] for f in wanted), 0
        for f in wanted:
            _check_cancel(cancel)
            progress("Restoring files", done_b, total_b, f["path"])
            try:
                target = safe_join(dest, f["path"])
                if target.exists():
                    if conflict == "skip":
                        result.skipped_existing += 1
                        done_b += f["size"]
                        continue
                    if conflict == "keep_both":
                        target = self._unique_name(target)
                reasons = []
                for store in ready:
                    try:
                        self._restore_one(store, f, target, cancel)
                        result.restored += 1
                        result.bytes_written += f["size"]
                        break
                    except Cancelled:
                        raise
                    except (StoreError, HashMismatch, OSError) as err:
                        reasons.append(f"{store.label}: {getattr(err, 'strerror', None) or err}")
                else:
                    result.failed.append((f["path"], "; ".join(reasons)))
            except Cancelled:
                raise
            except SafeFileError as err:
                result.failed.append((f["path"], str(err)))
            done_b += f["size"]
        level = "success" if not result.failed else "warning"
        db.log(level, "Restore", f"Restored {result.restored} file(s) from {snap['id']}",
               f"To {dest}. {len(result.failed)} failed, {result.skipped_existing} skipped.")
        return result

    @staticmethod
    def _unique_name(target: Path) -> Path:
        n = 1
        while True:
            tag = " (restored)" if n == 1 else f" (restored {n})"
            cand = target.with_name(f"{target.stem}{tag}{target.suffix}")
            if not cand.exists():
                return cand
            n += 1

    @staticmethod
    def _restore_one(store, f, target: Path, cancel):
        import hashlib
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".safefile-{uuid.uuid4().hex[:8]}.tmp")
        h = hashlib.sha256()
        try:
            with open(tmp, "wb") as out:
                for block in store.read_blob(f["sha256"]):
                    _check_cancel(cancel)
                    h.update(block)
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
            if h.hexdigest() != f["sha256"]:
                raise HashMismatch("restored data failed its integrity check")
            os.replace(tmp, target)
            try:
                os.utime(target, ns=(f["mtime_ns"], f["mtime_ns"]))
            except OSError:
                pass
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    # ================================================================ retention
    def apply_retention(self, project_id=None, grace_seconds=3600) -> dict:
        """Delete old *verified* versions beyond the retention policy, then free unreferenced blobs."""
        policy = parse_retention(self.settings().get("retention", ""))
        report = {"deleted": 0, "freed_blobs": 0}
        if policy is None:
            return report
        daily, monthly = policy
        projects = [self.db.get_project(project_id)] if project_id else self.db.list_projects("project")
        projects = [p for p in projects if p and p["kind"] == "project"]
        touched: set = set()
        for p in projects:
            verified = [s for s in self.db.list_snapshots(p["id"]) if s["state"] == "verified"]
            keep = select_to_keep(
                [(s["id"], parse_iso(s["created_at"]).astimezone()) for s in verified], daily, monthly)
            for s in verified:
                if s["id"] in keep:
                    continue
                for sid in json.loads(s["destinations"]):
                    touched.add(sid)
                    self._delete_manifest(sid, s["id"])
                self.db.delete_snapshot(s["seq"])
                report["deleted"] += 1
        if report["deleted"]:
            report["freed_blobs"] = self._gc(touched, grace_seconds)
            self.db.log("info", "Retention", f"Removed {report['deleted']} old version(s)",
                        f"{report['freed_blobs']} unused item(s) freed")
        return report

    def _delete_manifest(self, store_id, snapshot_id):
        try:
            store_from_id(store_id, self.settings()).delete_named(f"snapshots/{snapshot_id}.json")
        except SafeFileError:
            pass

    def _gc(self, store_ids, grace_seconds) -> int:
        freed, settings = 0, self.settings()
        for sid in store_ids:
            try:
                store = store_from_id(sid, settings)
                referenced = self.db.referenced_hashes(sid)
                cutoff = time.time() - grace_seconds
                for sha, mtime in list(store.list_blobs()):
                    if sha not in referenced and mtime < cutoff:
                        store.delete_blob(sha)
                        freed += 1
            except SafeFileError:
                continue
        return freed

    def remove_project(self, project_id, progress=None):
        """Forget a project and its version history; free the data only it used."""
        progress = progress or _noop
        p = self.db.get_project(project_id)
        if not p:
            return
        touched = set()
        for s in self.db.list_snapshots(project_id):
            for sid in json.loads(s["destinations"]):
                touched.add(sid)
                self._delete_manifest(sid, s["id"])
        self.db.delete_project(project_id)
        progress("Freeing unused backup data", 0, 0, "")
        freed = self._gc(touched, grace_seconds=3600)
        self.db.log("info", "Project", f"Removed project {p['name']}", f"{freed} unused item(s) freed")
