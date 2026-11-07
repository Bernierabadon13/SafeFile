"""Folder scanning, hashing, manifests and retention rules (no storage, no database)."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime

from .errors import Cancelled

CHUNK = 1024 * 1024
_REPARSE_POINT = 0x400  # Windows junctions / mount points


@dataclass
class FileEntry:
    path: str          # relative to the project folder, always '/' separated
    abs_path: str
    size: int
    mtime_ns: int
    sha256: str = ""


def hash_file(path, on_bytes=None, cancel=None):
    """Return (sha256 hex, bytes read)."""
    h = hashlib.sha256()
    done = 0
    with open(path, "rb") as f:
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
            done += len(block)
            if on_bytes:
                on_bytes(done)
    return h.hexdigest(), done


def sha256_file(path, cancel=None) -> str:
    return hash_file(path, cancel=cancel)[0]


def matches_exclusion(rel: str, name: str, patterns) -> bool:
    rel_l, name_l = rel.lower(), name.lower()
    for pattern in patterns:
        p = pattern.strip().lower().replace("\\", "/")
        if p and (fnmatch.fnmatchcase(name_l, p) or fnmatch.fnmatchcase(rel_l, p)):
            return True
    return False


def _is_link(st) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


def scan_folder(root, patterns, cancel=None, on_count=None):
    """Walk `root`. Returns (entries, skipped[(path, reason)]). Links are not followed."""
    root = os.path.abspath(root)
    if os.path.isfile(root):  # a dropped single file
        try:
            st = os.stat(root)
        except OSError as err:
            return [], [(os.path.basename(root), err.strerror or str(err))]
        return [FileEntry(os.path.basename(root), root, st.st_size, st.st_mtime_ns)], []
    entries, skipped = [], []

    def on_error(err):
        skipped.append((str(getattr(err, "filename", "") or "?"), err.strerror or str(err)))

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=on_error):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        kept = []
        for d in dirnames:
            rel = f"{rel_dir}/{d}" if rel_dir else d
            if matches_exclusion(rel, d, patterns):
                continue
            try:
                if _is_link(os.lstat(os.path.join(dirpath, d))):
                    continue
            except OSError:
                continue
            kept.append(d)
        dirnames[:] = kept
        for name in filenames:
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if matches_exclusion(rel, name, patterns):
                continue
            full = os.path.join(dirpath, name)
            try:
                st = os.lstat(full)
            except OSError as err:
                skipped.append((rel, err.strerror or str(err)))
                continue
            if _is_link(st) or not stat.S_ISREG(st.st_mode):
                continue
            entries.append(FileEntry(rel, full, st.st_size, st.st_mtime_ns))
        if on_count:
            on_count(len(entries))
    return entries, skipped


def build_manifest(snapshot_id, project_name, created_iso, files, skipped) -> bytes:
    doc = {
        "format": 1,
        "snapshot": snapshot_id,
        "project": project_name,
        "created": created_iso,
        "files": [{"path": f.path, "sha256": f.sha256, "size": f.size, "mtime_ns": f.mtime_ns} for f in files],
        "skipped": [{"path": p, "reason": r} for p, r in skipped],
    }
    return json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8")


# ------------------------------------------------------------------ retention
def parse_retention(text: str):
    """'30 daily, 12 monthly' -> (30, 12). 'Keep everything' -> None."""
    t = (text or "").lower().strip()
    if t.startswith("keep everything") or not t:
        return None
    daily = re.search(r"(\d+)\s*daily", t)
    monthly = re.search(r"(\d+)\s*monthly", t)
    return (int(daily.group(1)) if daily else 0, int(monthly.group(1)) if monthly else 0)


def select_to_keep(snaps, daily: int, monthly: int, keep_within_hours: int = 24, now=None) -> set:
    """snaps: iterable of (snapshot_id, timezone-aware datetime). Keeps:
    - every version from the last `keep_within_hours` hours,
    - the newest version of each of the last `daily` distinct days,
    - the newest version of each of the last `monthly` distinct months,
    - and always the single newest version."""
    from datetime import timedelta, timezone
    now = now or datetime.now(timezone.utc)
    ordered = sorted(snaps, key=lambda s: s[1], reverse=True)
    keep = set()
    if not ordered:
        return keep
    keep.add(ordered[0][0])
    cutoff = now - timedelta(hours=keep_within_hours)
    days, months = [], []
    for sid, dt in ordered:
        if dt >= cutoff:
            keep.add(sid)
        day, month = dt.date(), (dt.year, dt.month)
        if day not in days and len(days) < daily:
            days.append(day)
            keep.add(sid)
        if month not in months and len(months) < monthly:
            months.append(month)
            keep.add(sid)
    return keep


def sort_key_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)
