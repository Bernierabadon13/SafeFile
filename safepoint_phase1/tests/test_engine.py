"""Engine tests (no GUI needed):  python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from safepoint.db.database import Database
from safepoint.engine.engine import BackupEngine, safe_join
from safepoint.engine.core import parse_retention, select_to_keep
from safepoint.engine.errors import SafeFileError, StoreError
from safepoint.engine.minicloud import MiniCloudServer
from safepoint.engine.stores import CloudStore


def write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.src, self.backups, self.restore_dir, self.cloud_root = t / "src", t / "backups", t / "restore", t / "cloud"
        write(self.src / "a.txt", b"hello")
        write(self.src / "docs" / "b.txt", b"world" * 1000)
        write(self.src / "docs" / "deep" / "c.bin", os.urandom(300_000))
        write(self.src / "node_modules" / "skip.js", b"x")
        write(self.src / "tmp.tmp", b"x")
        self.db = Database(t / "test.db")
        self.engine = BackupEngine(self.db)
        self.db.set_setting("local_path", str(self.backups))
        self.db.set_setting("cloud_mode", "off")
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            s.stop()
        self.tmp.cleanup()

    def project(self, destination="local"):
        return self.db.add_project("Proj", str(self.src), destination, "Manual only", ["node_modules", "*.tmp"])

    def start_cloud(self, token="secret"):
        server = MiniCloudServer(self.cloud_root, token, "127.0.0.1", 0)
        server.start()
        self.servers.append(server)
        self.db.set_setting("cloud_mode", "remote")
        self.db.set_setting("cloud_url", server.url)
        self.db.set_setting("cloud_token", token)
        return server


class LocalTests(Base):
    def test_backup_verify_restore_roundtrip(self):
        pid = self.project()
        r = self.engine.backup(pid)
        self.assertEqual(r.status, "verified")
        self.assertEqual(r.files, 3)  # exclusions honoured
        self.assertEqual(self.db.get_snapshot(r.snapshot_id)["state"], "verified")
        res = self.engine.restore(r.snapshot_id, ["a.txt", "docs/b.txt", "docs/deep/c.bin"], self.restore_dir)
        self.assertEqual((res.restored, res.failed), (3, []))
        for rel in ("a.txt", "docs/b.txt", "docs/deep/c.bin"):
            self.assertEqual((self.restore_dir / rel).read_bytes(), (self.src / rel).read_bytes())

    def test_unchanged_then_change_detection(self):
        pid = self.project()
        first = self.engine.backup(pid)
        self.assertEqual(self.engine.backup(pid).status, "unchanged")
        write(self.src / "a.txt", b"hello again")
        write(self.src / "new.txt", b"new")
        (self.src / "docs" / "b.txt").unlink()
        r = self.engine.backup(pid)
        self.assertEqual((r.status, r.added, r.modified, r.removed), ("verified", 1, 1, 1))
        self.assertNotEqual(r.snapshot_id, first.snapshot_id)

    def test_dedup_does_not_store_twice(self):
        write(self.src / "copy_of_a.txt", b"hello")
        self.engine.backup(self.project())
        blobs = list((self.backups / "SafeFile" / "objects").rglob("*"))
        self.assertEqual(len([b for b in blobs if b.is_file()]), 3)  # a/copy share one blob

    def test_corruption_is_detected_not_hidden(self):
        r = self.engine.backup(self.project())
        victim = next((self.backups / "SafeFile" / "objects").rglob("*"))
        while victim.is_dir():
            victim = next(victim.iterdir())
        victim.write_bytes(b"corrupted")
        v = self.engine.verify(r.snapshot_id)
        self.assertEqual(v.state, "failed")
        self.assertEqual(self.db.get_snapshot(r.snapshot_id)["state"], "failed")

    def test_destination_inside_source_is_refused(self):
        self.db.set_setting("local_path", str(self.src / "inner"))
        with self.assertRaises(StoreError):
            self.engine.backup(self.project())
        self.assertIsNotNone(self.db.get_project(1)["last_error"])

    def test_unset_local_path_gives_clear_error(self):
        self.db.set_setting("local_path", "")
        with self.assertRaises(StoreError):
            self.engine.backup(self.project())

    def test_restore_conflict_modes_and_traversal(self):
        r = self.engine.backup(self.project())
        write(self.restore_dir / "a.txt", b"existing")
        self.engine.restore(r.snapshot_id, ["a.txt"], self.restore_dir, "skip")
        self.assertEqual((self.restore_dir / "a.txt").read_bytes(), b"existing")
        self.engine.restore(r.snapshot_id, ["a.txt"], self.restore_dir, "keep_both")
        self.assertEqual((self.restore_dir / "a (restored).txt").read_bytes(), b"hello")
        self.assertEqual((self.restore_dir / "a.txt").read_bytes(), b"existing")
        self.engine.restore(r.snapshot_id, ["a.txt"], self.restore_dir, "overwrite")
        self.assertEqual((self.restore_dir / "a.txt").read_bytes(), b"hello")
        with self.assertRaises(SafeFileError):
            safe_join(self.restore_dir, "../evil.txt")
        with self.assertRaises(SafeFileError):
            safe_join(self.restore_dir, "C:/evil.txt")

    def test_cancel_leaves_no_snapshot(self):
        from safepoint.engine.errors import Cancelled
        ev = threading.Event()
        ev.set()
        pid = self.project()
        with self.assertRaises(Cancelled):
            self.engine.backup(pid, cancel=ev)
        self.assertEqual(self.db.list_snapshots(pid), [])


class CloudTests(Base):
    def test_cloud_backup_and_restore(self):
        self.start_cloud()
        r = self.engine.backup(self.project("cloud"))
        self.assertEqual(r.status, "verified")
        self.assertTrue(any((self.cloud_root / "objects").rglob("*")))
        res = self.engine.restore(r.snapshot_id, ["docs/b.txt"], self.restore_dir)
        self.assertEqual(res.restored, 1)
        self.assertEqual((self.restore_dir / "docs" / "b.txt").read_bytes(), (self.src / "docs" / "b.txt").read_bytes())

    def test_wrong_token_is_rejected(self):
        server = self.start_cloud("right")
        self.db.set_setting("cloud_token", "wrong")
        with self.assertRaises(StoreError) as cm:
            self.engine.backup(self.project("cloud"))
        self.assertIn("token", str(cm.exception))

    def test_unreachable_cloud_is_reported(self):
        server = self.start_cloud()
        server.stop()
        with self.assertRaises(StoreError):
            self.engine.backup(self.project("cloud"))

    def test_both_destinations_and_fallback_restore(self):
        self.start_cloud()
        r = self.engine.backup(self.project("both"))
        self.assertEqual(r.status, "verified")
        self.assertEqual(len(json.loads(self.db.get_snapshot(r.snapshot_id)["destinations"])), 2)
        # damage the local copy: verification must fail, restore must fall back to the cloud copy
        for f in (self.backups / "SafeFile" / "objects").rglob("*"):
            if f.is_file():
                f.write_bytes(b"broken")
        self.assertEqual(self.engine.verify(r.snapshot_id).state, "failed")
        res = self.engine.restore(r.snapshot_id, ["a.txt", "docs/b.txt"], self.restore_dir)
        self.assertEqual((res.restored, res.failed), (2, []))
        self.assertEqual((self.restore_dir / "a.txt").read_bytes(), b"hello")

    def test_server_rejects_bad_hash_upload(self):
        server = self.start_cloud()
        store = CloudStore(server.url, "secret")
        bad = self.src / "a.txt"
        with self.assertRaises(Exception):
            store.put_blob("0" * 64, bad, bad.stat().st_size)


class RetentionTests(Base):
    def test_policy_parsing_and_selection(self):
        self.assertEqual(parse_retention("30 daily, 12 monthly"), (30, 12))
        self.assertEqual(parse_retention("7 daily"), (7, 0))
        self.assertIsNone(parse_retention("Keep everything"))
        now = datetime.now(timezone.utc)
        snaps = [(f"s{i}", now - timedelta(days=i)) for i in range(10)]
        self.assertEqual(select_to_keep(snaps, 3, 0), {"s0", "s1", "s2"})

    def test_prune_removes_old_versions_and_unused_data(self):
        self.db.set_setting("retention", "2 daily")
        pid = self.project()
        ids = []
        for i in range(4):
            write(self.src / "a.txt", f"version {i}".encode())
            ids.append(self.engine.backup(pid).snapshot_id)
        # age the first three versions onto different past days
        with self.db.tx() as c:
            for n, sid in enumerate(ids):
                c.execute("UPDATE snapshots SET created_at=? WHERE id=?",
                          ((datetime.now(timezone.utc) - timedelta(days=10 - n)).isoformat(timespec="seconds"), sid))
        report = self.engine.apply_retention(pid, grace_seconds=-1)
        self.assertEqual(report["deleted"], 2)
        remaining = [s["id"] for s in self.db.list_snapshots(pid)]
        self.assertEqual(sorted(remaining), sorted(ids[2:]))
        # old content is gone, current content still restorable and verified
        self.assertEqual(self.engine.verify(ids[3]).state, "verified")
        self.engine.restore(ids[3], ["a.txt"], self.restore_dir)
        self.assertEqual((self.restore_dir / "a.txt").read_bytes(), b"version 3")

    def test_remove_project_frees_data(self):
        pid = self.project()
        self.engine.backup(pid)
        self.engine.remove_project(pid)
        self.assertIsNone(self.db.get_project(pid))


if __name__ == "__main__":
    unittest.main()


class RepositoryTests(Base):
    def setUp(self):
        super().setUp()
        from safepoint.db.sqlite_repository import SqliteRepository
        self.repo = SqliteRepository(self.db)

    def test_models_status_tree_changes_missing_and_schedule(self):
        pid = self.repo.add_project("Proj", str(self.src), "local", "Every hour", ["node_modules"])
        p = self.repo.get_projects()[0]
        self.assertEqual((p.status_label, p.status_kind), ("No backup yet", "info"))
        self.assertEqual([d.id for d in self.repo.due_projects()], [str(pid)])  # never backed up -> due
        r = self.engine.backup(pid, "Scheduled")
        p = self.repo.get_projects()[0]
        self.assertEqual((p.status_label, p.status_kind), ("Protected", "success"))
        self.assertEqual(self.repo.due_projects(), [])
        snap = self.repo.get_snapshots()[0]
        self.assertEqual((snap.id, snap.verification, snap.kind), (r.snapshot_id, "Verified", "Scheduled"))
        tree = self.repo.get_restore_tree(snap.id)
        names = [n.name for n in tree]
        self.assertIn("docs", names)
        docs = next(n for n in tree if n.name == "docs")
        self.assertTrue(docs.is_folder and any(c.path == "docs/b.txt" for c in docs.children))
        self.assertEqual({c.change for c in self.repo.get_changed_files(snap.id)}, {"Added"})
        (self.src / "a.txt").unlink()
        missing = self.repo.get_missing_files()
        self.assertEqual([m.rel_path for m in missing], ["a.txt"])
        # a failed backup shows as an error status
        self.db.set_setting("local_path", "")
        with self.assertRaises(StoreError):
            self.engine.backup(pid)
        self.assertEqual(self.repo.get_projects()[0].status_label, "Backup failed")


class QuickSaveTests(Base):
    def setUp(self):
        super().setUp()
        from safepoint.db.sqlite_repository import SqliteRepository
        self.repo = SqliteRepository(self.db)

    def test_file_history_is_separate_and_every_save_is_a_version(self):
        f = self.src / "a.txt"
        r1 = self.engine.quick_save(str(f), "local", "first")
        r2 = self.engine.quick_save(str(f), "local")             # same content, saved on request
        f.write_bytes(b"changed")
        r3 = self.engine.quick_save(str(f), "local", "after edit")
        self.assertEqual([r1.status, r2.status, r3.status], ["verified"] * 3)
        self.assertEqual(len({r1.snapshot_id, r2.snapshot_id, r3.snapshot_id}), 3)
        items = self.repo.get_quick_items()
        self.assertEqual((len(items), items[0].versions, items[0].is_folder), (1, 3, False))
        versions = self.repo.get_item_snapshots(items[0].id)
        self.assertEqual([v.kind for v in versions], ["Quick save"] * 3)
        self.assertIn("Same content", versions[1].note)   # newest first: [after edit, same, first]
        self.assertIn("after edit", versions[0].note)
        # a quick save never shows up in the project lists
        self.assertEqual(self.repo.get_snapshots(), [])
        self.assertEqual(self.repo.get_projects(), [])
        self.assertEqual(self.repo.due_projects(), [])

    def test_each_version_restores_its_own_content(self):
        f = self.src / "a.txt"
        v1 = self.engine.quick_save(str(f), "local")
        f.write_bytes(b"second")
        v2 = self.engine.quick_save(str(f), "local")
        d1, d2 = self.restore_dir / "one", self.restore_dir / "two"
        for snap, dest in ((v1, d1), (v2, d2)):
            res = self.engine.restore(snap.snapshot_id, self.repo.get_snapshot_paths(snap.snapshot_id), dest)
            self.assertEqual(res.failed, [])
        self.assertEqual((d1 / "a.txt").read_bytes(), b"hello")
        self.assertEqual((d2 / "a.txt").read_bytes(), b"second")

    def test_folder_item_and_both_destinations(self):
        self.start_cloud()
        r = self.engine.quick_save(str(self.src), "both")
        self.assertEqual(r.status, "verified")
        self.assertEqual(r.files, 3)  # default exclusions apply to dropped folders (node_modules, *.tmp)
        item = self.repo.get_quick_items()[0]
        self.assertTrue(item.is_folder)

    def test_quick_versions_are_never_pruned(self):
        self.db.set_setting("retention", "1 daily")
        f = self.src / "a.txt"
        ids = []
        for i in range(3):
            f.write_bytes(f"v{i}".encode())
            ids.append(self.engine.quick_save(str(f), "local").snapshot_id)
        with self.db.tx() as c:
            for n, sid in enumerate(ids):
                c.execute("UPDATE snapshots SET created_at=? WHERE id=?",
                          ((datetime.now(timezone.utc) - timedelta(days=20 - n)).isoformat(timespec="seconds"), sid))
        self.assertEqual(self.engine.apply_retention()["deleted"], 0)
        self.assertEqual(len(self.repo.get_item_snapshots(self.repo.get_quick_items()[0].id)), 3)

    def test_missing_original_is_flagged_and_still_restorable(self):
        f = self.src / "a.txt"
        r = self.engine.quick_save(str(f), "local")
        f.unlink()
        item = self.repo.get_quick_items()[0]
        self.assertEqual(item.status_label, "Original missing")
        res = self.engine.restore(r.snapshot_id, ["a.txt"], self.src)
        self.assertEqual(res.restored, 1)
        self.assertEqual(f.read_bytes(), b"hello")

    def test_old_database_is_migrated(self):
        import sqlite3
        old = Path(self.tmp.name) / "old.db"
        con = sqlite3.connect(old)
        con.executescript("CREATE TABLE projects(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, path TEXT NOT NULL,"
                          " category TEXT NOT NULL DEFAULT 'General', destination TEXT NOT NULL DEFAULT 'local',"
                          " schedule TEXT NOT NULL DEFAULT 'Every hour', exclusions TEXT NOT NULL DEFAULT '[]',"
                          " paused INTEGER NOT NULL DEFAULT 0, last_error TEXT, last_ok_at TEXT, last_attempt_at TEXT,"
                          " created_at TEXT NOT NULL); INSERT INTO projects(name,path,created_at) VALUES('P','x','2026-01-01T00:00:00+00:00');")
        con.commit(); con.close()
        db = Database(old)
        self.assertEqual([p["kind"] for p in db.list_projects()], ["project"])
