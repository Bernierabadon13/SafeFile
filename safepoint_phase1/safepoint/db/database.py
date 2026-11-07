"""SQLite storage for projects, snapshots (version history), file manifests, settings and the activity log."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

from safepoint.util import utcnow_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    kind TEXT NOT NULL DEFAULT 'project',
    destination TEXT NOT NULL DEFAULT 'local',
    schedule TEXT NOT NULL DEFAULT 'Every hour',
    exclusions TEXT NOT NULL DEFAULT '[]',
    paused INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_ok_at TEXT,
    last_attempt_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots(
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    state TEXT NOT NULL,
    destinations TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER NOT NULL DEFAULT 0,
    added INTEGER NOT NULL DEFAULT 0,
    modified INTEGER NOT NULL DEFAULT 0,
    removed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    verified_at TEXT
);
CREATE TABLE IF NOT EXISTS snapshot_files(
    snapshot_seq INTEGER NOT NULL REFERENCES snapshots(seq) ON DELETE CASCADE,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    PRIMARY KEY(snapshot_seq, path)
);
CREATE TABLE IF NOT EXISTS activity(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    category TEXT NOT NULL,
    message TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_snapshots_project ON snapshots(project_id, seq);
"""


class Database:
    def __init__(self, path):
        self.path = str(path)
        with self.tx() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SCHEMA)
            cols = {r["name"] for r in con.execute("PRAGMA table_info(projects)")}
            if "kind" not in cols:  # databases created before quick saves existed
                con.execute("ALTER TABLE projects ADD COLUMN kind TEXT NOT NULL DEFAULT 'project'")

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def tx(self):
        con = self._connect()
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _d(row):
        return dict(row) if row is not None else None

    # ------------------------------------------------------------ settings
    def get_setting(self, key, default=None):
        with self.tx() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def set_setting(self, key, value):
        with self.tx() as c:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def all_settings(self, defaults):
        data = dict(defaults)
        with self.tx() as c:
            for r in c.execute("SELECT key,value FROM settings"):
                data[r["key"]] = json.loads(r["value"])
        return data

    # ------------------------------------------------------------ projects
    def add_project(self, name, path, destination, schedule, exclusions, category="General", kind="project"):
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO projects(name,path,category,kind,destination,schedule,exclusions,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (name, path, category, kind, destination, schedule, json.dumps(list(exclusions)), utcnow_iso()))
            return cur.lastrowid

    def find_quick_item(self, path):
        with self.tx() as c:
            return self._d(c.execute("SELECT * FROM projects WHERE kind='quick' AND lower(path)=lower(?)",
                                     (path,)).fetchone())

    def update_project(self, project_id, **fields):
        allowed = {"name", "path", "destination", "schedule", "paused", "exclusions"}
        sets, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                raise KeyError(k)
            sets.append(f"{k}=?")
            vals.append(json.dumps(list(v)) if k == "exclusions" else (int(v) if k == "paused" else v))
        if sets:
            with self.tx() as c:
                c.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", (*vals, project_id))

    def delete_project(self, project_id):
        with self.tx() as c:
            c.execute("DELETE FROM projects WHERE id=?", (project_id,))

    def get_project(self, project_id):
        with self.tx() as c:
            return self._d(c.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())

    def list_projects(self, kind=None):
        with self.tx() as c:
            if kind:
                return [dict(r) for r in c.execute("SELECT * FROM projects WHERE kind=? ORDER BY id", (kind,))]
            return [dict(r) for r in c.execute("SELECT * FROM projects ORDER BY id")]

    def set_project_error(self, project_id, message):
        with self.tx() as c:
            c.execute("UPDATE projects SET last_error=? WHERE id=?", (message, project_id))

    def touch_attempt(self, project_id):
        with self.tx() as c:
            c.execute("UPDATE projects SET last_attempt_at=? WHERE id=?", (utcnow_iso(), project_id))

    def mark_ok(self, project_id):
        with self.tx() as c:
            c.execute("UPDATE projects SET last_ok_at=?, last_error=NULL WHERE id=?", (utcnow_iso(), project_id))

    # ------------------------------------------------------------ snapshots
    def purge_incomplete(self):
        with self.tx() as c:
            c.execute("DELETE FROM snapshots WHERE state='writing'")

    def begin_snapshot(self, project_id, kind, destination_ids):
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO snapshots(project_id,created_at,kind,state,destinations) VALUES(?,?,?,?,?)",
                (project_id, utcnow_iso(), kind, "writing", json.dumps(list(destination_ids))))
            seq = cur.lastrowid
            sid = f"snap-{seq:04d}"
            c.execute("UPDATE snapshots SET id=? WHERE seq=?", (sid, seq))
        return seq, sid

    def finish_snapshot(self, seq, files, added, modified, removed, skipped, note):
        with self.tx() as c:
            c.executemany("INSERT INTO snapshot_files(snapshot_seq,path,sha256,size,mtime_ns) VALUES(?,?,?,?,?)",
                          [(seq, *f) for f in files])
            c.execute(
                "UPDATE snapshots SET state='pending', file_count=?, total_bytes=?, added=?, modified=?, "
                "removed=?, skipped=?, note=? WHERE seq=?",
                (len(files), sum(f[2] for f in files), added, modified, removed, skipped, note, seq))

    def abort_snapshot(self, seq):
        with self.tx() as c:
            c.execute("DELETE FROM snapshots WHERE seq=?", (seq,))

    def set_snapshot_state(self, seq, state, detail=""):
        with self.tx() as c:
            c.execute("UPDATE snapshots SET state=?, detail=?, verified_at=? WHERE seq=?",
                      (state, detail, utcnow_iso() if state == "verified" else None, seq))

    _SNAP_SELECT = ("SELECT s.*, p.name AS project_name, p.path AS project_path, p.kind AS project_kind "
                    "FROM snapshots s JOIN projects p ON p.id=s.project_id ")

    def list_snapshots(self, project_id=None, kind=None):
        sql = self._SNAP_SELECT + "WHERE s.state!='writing' "
        args = ()
        if project_id is not None:
            sql += "AND s.project_id=? "
            args = (project_id,)
        if kind is not None:
            sql += "AND p.kind=? "
            args = (*args, kind)
        with self.tx() as c:
            return [dict(r) for r in c.execute(sql + "ORDER BY s.seq DESC", args)]

    def get_snapshot(self, snapshot_id):
        with self.tx() as c:
            return self._d(c.execute(self._SNAP_SELECT + "WHERE s.id=?", (snapshot_id,)).fetchone())

    def latest_snapshot(self, project_id, before_seq=None):
        sql = self._SNAP_SELECT + "WHERE s.project_id=? AND s.state!='writing' "
        args = [project_id]
        if before_seq is not None:
            sql += "AND s.seq<? "
            args.append(before_seq)
        with self.tx() as c:
            return self._d(c.execute(sql + "ORDER BY s.seq DESC LIMIT 1", args).fetchone())

    def delete_snapshot(self, seq):
        self.abort_snapshot(seq)

    def snapshot_files(self, seq):
        with self.tx() as c:
            return [dict(r) for r in c.execute(
                "SELECT path,sha256,size,mtime_ns FROM snapshot_files WHERE snapshot_seq=? ORDER BY path", (seq,))]

    def snapshot_file_map(self, seq):
        return {f["path"]: f for f in self.snapshot_files(seq)}

    def referenced_hashes(self, store_id):
        needle = json.dumps(store_id)
        with self.tx() as c:
            rows = c.execute(
                "SELECT DISTINCT f.sha256 FROM snapshot_files f JOIN snapshots s ON s.seq=f.snapshot_seq "
                "WHERE s.state!='writing' AND instr(s.destinations, ?) > 0", (needle,))
            return {r["sha256"] for r in rows}

    # ------------------------------------------------------------ activity
    def log(self, level, category, message, detail=""):
        with self.tx() as c:
            c.execute("INSERT INTO activity(ts,level,category,message,detail) VALUES(?,?,?,?,?)",
                      (utcnow_iso(), level, category, message, detail))
            c.execute("DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 2000)")

    def list_activity(self, limit=200):
        with self.tx() as c:
            return [dict(r) for r in c.execute("SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,))]
