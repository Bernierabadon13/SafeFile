"""Turns database rows into the UI models and exposes the write operations the screens need."""
from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone

from safepoint.config import DESTINATIONS, SCHEDULES, default_settings
from safepoint.data.models import ActivityEntry, ChangedFile, MissingFile, Project, QuickItem, Snapshot, TreeNode
from safepoint.db.database import Database
from safepoint.util import fmt_dt, human_size, parse_iso

_STATE_LABELS = {
    "verified": ("Verified", "success"),
    "pending": ("Pending", "info"),
    "failed": ("Failed", "error"),
}


class SqliteRepository:
    def __init__(self, db: Database):
        self.db = db
        if not self.db.get_setting("cloud_embedded_token"):
            self.db.set_setting("cloud_embedded_token", secrets.token_urlsafe(24))

    # ------------------------------------------------------------ settings
    def get_settings(self) -> dict:
        return self.db.all_settings(default_settings())

    def save_settings(self, values: dict):
        for key, value in values.items():
            self.db.set_setting(key, value)

    # ------------------------------------------------------------ projects
    def get_projects(self):
        now = datetime.now(timezone.utc)
        return [self._project(r, self.db.latest_snapshot(r["id"]), now) for r in self.db.list_projects("project")]

    def get_project(self, project_id):
        r = self.db.get_project(int(project_id))
        return self._project(r, self.db.latest_snapshot(r["id"]), datetime.now(timezone.utc)) if r else None

    def _project(self, r, latest, now) -> Project:
        label, kind, note = self._status(r, latest, now)
        return Project(
            id=str(r["id"]), name=r["name"], category=r["category"], path=r["path"],
            destination=DESTINATIONS.get(r["destination"], r["destination"]), schedule=r["schedule"],
            last_snapshot=fmt_dt(latest["created_at"]) if latest else "Never",
            size=human_size(latest["total_bytes"]) if latest else "—",
            file_count=latest["file_count"] if latest else 0,
            status_label=label, status_kind=kind, note=note,
            exclusions=tuple(json.loads(r["exclusions"])), destination_key=r["destination"],
            paused=bool(r["paused"]), last_ok=fmt_dt(r["last_ok_at"]),
        )

    @staticmethod
    def _status(r, latest, now):
        if r["paused"]:
            return "Paused", "neutral", "Automatic backups are paused for this project."
        if r["last_error"]:
            return "Backup failed", "error", r["last_error"]
        if not latest:
            return "No backup yet", "info", "Press Back Up Now to make the first backup."
        if latest["state"] == "failed":
            return "Verification failed", "error", latest["detail"] or "The latest version did not pass verification."
        if latest["state"] == "pending":
            return "Verification pending", "info", "The latest version has not been verified yet."
        if latest["skipped"]:
            return "Backed up with warnings", "warning", latest["note"]
        interval = SCHEDULES.get(r["schedule"])
        if interval:
            last = parse_iso(r["last_ok_at"]) or parse_iso(r["created_at"])
            if (now - last).total_seconds() > interval * 2 + 600:
                return "Backup overdue", "warning", "The last successful backup is older than the schedule allows."
        return "Protected", "success", ""

    def add_project(self, name, path, destination, schedule, exclusions):
        return self.db.add_project(name, path, destination, schedule, exclusions)

    def update_project(self, project_id, **fields):
        self.db.update_project(int(project_id), **fields)

    def due_projects(self, now_ts=None):
        now = datetime.fromtimestamp(now_ts or time.time(), timezone.utc)
        out = []
        for r in self.db.list_projects("project"):
            interval = SCHEDULES.get(r["schedule"])
            if r["paused"] or not interval:
                continue
            marks = [parse_iso(r["last_ok_at"]), parse_iso(r["last_attempt_at"])]
            marks = [m for m in marks if m]
            if not marks or (now - max(marks)).total_seconds() >= interval:
                out.append(self._project(r, self.db.latest_snapshot(r["id"]), now))
        return out

    # ------------------------------------------------------------ snapshots
    def get_snapshots(self, kind="project"):
        return [self._snapshot(r) for r in self.db.list_snapshots(kind=kind)]

    def get_snapshot(self, snapshot_id):
        r = self.db.get_snapshot(snapshot_id)
        return self._snapshot(r) if r else None

    @staticmethod
    def _snapshot(r) -> Snapshot:
        label, kind = _STATE_LABELS.get(r["state"], (r["state"].title(), "neutral"))
        return Snapshot(
            id=r["id"], project=r["project_name"], created=fmt_dt(r["created_at"]), kind=r["kind"],
            files=r["file_count"], size=human_size(r["total_bytes"]), verification=label,
            verification_kind=kind, added=r["added"], modified=r["modified"], removed=r["removed"],
            note=r["note"], project_id=str(r["project_id"]), detail=r["detail"])

    def get_changed_files(self, snapshot_id):
        snap = self.db.get_snapshot(snapshot_id)
        if not snap:
            return []
        cur = self.db.snapshot_file_map(snap["seq"])
        prev_row = self.db.latest_snapshot(snap["project_id"], before_seq=snap["seq"])
        prev = self.db.snapshot_file_map(prev_row["seq"]) if prev_row else {}
        out = []
        for path, f in sorted(cur.items()):
            if path not in prev:
                out.append(ChangedFile("Added", path, human_size(f["size"])))
            elif prev[path]["sha256"] != f["sha256"]:
                out.append(ChangedFile("Modified", path, human_size(f["size"])))
        for path, f in sorted(prev.items()):
            if path not in cur:
                out.append(ChangedFile("Removed", path, human_size(f["size"])))
        return out[:500]

    def get_restore_tree(self, snapshot_id):
        snap = self.db.get_snapshot(snapshot_id)
        if not snap:
            return ()
        root: dict = {}
        for f in self.db.snapshot_files(snap["seq"]):
            node = root
            *folders, name = f["path"].split("/")
            for part in folders:
                node = node.setdefault(part, {})
            node[name] = f
        def build(level, prefix=""):
            out = []
            for name in sorted(level, key=lambda k: (self._is_file(level[k]), k.lower())):
                v = level[name]
                if self._is_file(v):
                    out.append(TreeNode(name, False, human_size(v["size"]),
                                        datetime.fromtimestamp(v["mtime_ns"] / 1e9).strftime("%b %d, %Y %H:%M"),
                                        (), v["path"]))
                else:
                    out.append(TreeNode(name, True, children=tuple(build(v))))
            return out
        return tuple(build(root))

    @staticmethod
    def _is_file(v) -> bool:
        return isinstance(v.get("sha256"), str) and "mtime_ns" in v

    def get_missing_files(self, limit=30, budget_seconds=2.0):
        """Files in each project's latest version that no longer exist in the live folder."""
        started, out = time.monotonic(), []
        for r in self.db.list_projects("project"):
            latest = self.db.latest_snapshot(r["id"])
            if not latest or latest["state"] == "failed" or not os.path.isdir(r["path"]):
                continue
            for f in self.db.snapshot_files(latest["seq"]):
                if time.monotonic() - started > budget_seconds:
                    return self._sorted_missing(out, limit)
                if not os.path.exists(os.path.join(r["path"], *f["path"].split("/"))):
                    folder = os.path.dirname(os.path.join(r["path"], *f["path"].split("/")))
                    out.append((f["mtime_ns"], MissingFile(os.path.basename(f["path"]), folder, latest["id"],
                                human_size(f["size"]), latest["id"], f["path"], str(r["id"]), r["name"])))
        return self._sorted_missing(out, limit)

    @staticmethod
    def _sorted_missing(items, limit):
        return [m for _t, m in sorted(items, key=lambda x: x[0], reverse=True)[:limit]]

    # ------------------------------------------------------------ quick saves (drag and drop)
    def get_quick_items(self):
        return [self._quick_item(r) for r in self.db.list_projects("quick")]

    def get_quick_item(self, item_id):
        r = self.db.get_project(int(item_id))
        return self._quick_item(r) if r and r["kind"] == "quick" else None

    def _quick_item(self, r) -> QuickItem:
        snaps = self.db.list_snapshots(r["id"])
        latest = snaps[0] if snaps else None
        exists = os.path.exists(r["path"])
        if r["last_error"] and not (latest and latest["state"] == "verified"):
            label, kind = "Save failed", "error"
        elif not latest:
            label, kind = "No versions", "info"
        elif latest["state"] == "failed":
            label, kind = "Verification failed", "error"
        elif latest["state"] == "pending":
            label, kind = "Not verified", "info"
        elif not exists:
            label, kind = "Original missing", "warning"
        else:
            label, kind = "Saved", "success"
        return QuickItem(
            id=str(r["id"]), name=r["name"], path=r["path"], is_folder=os.path.isdir(r["path"]),
            exists=exists, versions=len(snaps), last_saved=fmt_dt(latest["created_at"]) if latest else "Never",
            status_label=label, status_kind=kind,
            destination=DESTINATIONS.get(r["destination"], r["destination"]), destination_key=r["destination"])

    def get_item_snapshots(self, item_id):
        return [self._snapshot(r) for r in self.db.list_snapshots(int(item_id))]

    def get_snapshot_paths(self, snapshot_id):
        snap = self.db.get_snapshot(snapshot_id)
        return [f["path"] for f in self.db.snapshot_files(snap["seq"])] if snap else []

    # ------------------------------------------------------------ activity
    def get_activity(self):
        return [ActivityEntry(fmt_dt(r["ts"]), r["level"], r["category"], r["message"], r["detail"])
                for r in self.db.list_activity()]
