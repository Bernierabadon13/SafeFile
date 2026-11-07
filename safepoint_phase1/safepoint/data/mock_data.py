"""Static sample data for the Phase 1 prototype.

Nothing here reflects real files, backups or drives. Every value is invented.
"""
from __future__ import annotations

from .models import (
    ActivityEntry,
    ChangedFile,
    MissingFile,
    OverviewStats,
    Project,
    Snapshot,
    StorageLocation,
    TreeNode,
)

LOCAL = r"Local Folder (D:\SafeFileBackups)"
EXTERNAL = r"External Drive (E:\SafeFile)"

_PROJECTS = [
    Project("p1", "SafeFile Source", "Programming", r"C:\Users\Demo\Projects\safefile",
            EXTERNAL, "Every 30 minutes", "Oct 23, 2026 · 08:30", "148 MB", 1842,
            "Protected", "success", "Sample: latest snapshot marked verified.",
            ("__pycache__", ".venv", "*.tmp")),
    Project("p2", "Portfolio Website", "Programming", r"C:\Users\Demo\Projects\portfolio",
            LOCAL, "Every hour", "Oct 23, 2026 · 08:00", "62 MB", 413,
            "Protected", "success", "Sample: latest snapshot marked verified.",
            ("node_modules", "*.log")),
    Project("p3", "Thesis Draft", "Schoolwork", r"C:\Users\Demo\Documents\Thesis",
            EXTERNAL, "Daily at 20:00", "Oct 21, 2026 · 20:15", "214 MB", 96,
            "Backup overdue", "warning", "Sample: external drive not detected since Oct 21.",
            ("~$*", "*.tmp")),
    Project("p4", "Video Edit Archive", "Media", r"C:\Users\Demo\Videos\Edits",
            LOCAL, "Weekly (Sun 22:00)", "Oct 22, 2026 · 22:00", "38.4 GB", 2317,
            "Verification pending", "info", "Sample: snapshot waiting for verification.",
            ("Proxies", "Render Cache", "*.tmp")),
    Project("p5", "Lab Reports", "Schoolwork", r"C:\Users\Demo\Documents\Lab Reports",
            LOCAL, "Daily at 18:00", "Oct 20, 2026 · 18:02", "87 MB", 58,
            "Verification failed", "error", "Sample: last snapshot did not pass verification.",
            ("~$*",)),
    Project("p6", "Math Notes", "Schoolwork", r"C:\Users\Demo\Documents\Notes",
            LOCAL, "Paused", "Oct 12, 2026 · 19:30", "31 MB", 142,
            "Paused", "neutral", "Sample: protection paused by user.",
            ("Thumbs.db",)),
]

_SNAPSHOTS = [
    Snapshot("snap-0231", "SafeFile Source", "Oct 23, 2026 · 08:30", "Scheduled", 1842, "148 MB", "Verified", "success", 3, 12, 0),
    Snapshot("snap-0230", "SafeFile Source", "Oct 23, 2026 · 08:00", "Scheduled", 1839, "147 MB", "Verified", "success", 0, 7, 0),
    Snapshot("snap-0229", "Portfolio Website", "Oct 23, 2026 · 08:00", "Scheduled", 413, "62 MB", "Verified", "success", 1, 4, 0),
    Snapshot("snap-0228", "Video Edit Archive", "Oct 22, 2026 · 22:00", "Scheduled", 2317, "38.4 GB", "Pending", "info", 24, 6, 2),
    Snapshot("snap-0227", "SafeFile Source", "Oct 22, 2026 · 17:30", "Manual", 1839, "147 MB", "Verified", "success", 5, 18, 3, "Before UI refactor"),
    Snapshot("snap-0226", "Portfolio Website", "Oct 22, 2026 · 18:00", "Scheduled", 412, "61 MB", "Verified", "success", 0, 2, 0),
    Snapshot("snap-0225", "Thesis Draft", "Oct 21, 2026 · 20:15", "Scheduled", 96, "214 MB", "Verified", "success", 2, 5, 1),
    Snapshot("snap-0224", "Lab Reports", "Oct 20, 2026 · 18:02", "Manual", 58, "87 MB", "Failed", "error", 4, 1, 0, "Sample failure: integrity check mismatch"),
    Snapshot("snap-0223", "Thesis Draft", "Oct 20, 2026 · 20:00", "Scheduled", 95, "212 MB", "Verified", "success", 0, 3, 0),
    Snapshot("snap-0222", "Video Edit Archive", "Oct 15, 2026 · 22:00", "Scheduled", 2295, "37.9 GB", "Verified", "success", 31, 12, 0),
    Snapshot("snap-0221", "Math Notes", "Oct 12, 2026 · 19:30", "Scheduled", 142, "31 MB", "Verified", "success", 0, 2, 0),
]

_CHANGES = {
    "Programming": [
        ChangedFile("Added", r"src\ui\new_dialog.py", "4.1 KB"),
        ChangedFile("Modified", r"src\main.py", "12.8 KB"),
        ChangedFile("Modified", r"src\ui\sidebar.py", "6.3 KB"),
        ChangedFile("Modified", r"README.md", "2.2 KB"),
        ChangedFile("Removed", r"src\old_helpers.py", "3.0 KB"),
    ],
    "Schoolwork": [
        ChangedFile("Added", r"Chapter 4 - Results.docx", "312 KB"),
        ChangedFile("Modified", r"Chapter 3 - Methods.docx", "268 KB"),
        ChangedFile("Modified", r"References.bib", "18 KB"),
        ChangedFile("Removed", r"Scratch notes.txt", "1.1 KB"),
    ],
    "Media": [
        ChangedFile("Added", r"Projects\Edit_v7.aep", "46 MB"),
        ChangedFile("Added", r"Exports\Edit_v7_final.mp4", "1.8 GB"),
        ChangedFile("Modified", r"Projects\Edit_v6.aep", "44 MB"),
        ChangedFile("Removed", r"Exports\Edit_v5_draft.mp4", "1.2 GB"),
    ],
}

_ACTIVITY = [
    ActivityEntry("Oct 23 · 08:30", "success", "Snapshot", "Snapshot snap-0231 listed for SafeFile Source", "Sample entry. 1,842 files, 148 MB. Verification marked passed in sample data."),
    ActivityEntry("Oct 23 · 08:00", "success", "Snapshot", "Snapshot snap-0229 listed for Portfolio Website", "Sample entry. 413 files, 62 MB."),
    ActivityEntry("Oct 23 · 07:12", "warning", "Storage", r"External Drive (E:) not detected", "Sample warning. Projects targeting this drive would be marked overdue."),
    ActivityEntry("Oct 22 · 22:41", "info", "Verification", "Verification queued for snap-0228", "Sample entry. Large snapshot (38.4 GB) waiting in queue."),
    ActivityEntry("Oct 22 · 17:30", "info", "Snapshot", "Manual snapshot snap-0227 requested for SafeFile Source", "Sample note: Before UI refactor."),
    ActivityEntry("Oct 21 · 20:15", "success", "Snapshot", "Snapshot snap-0225 listed for Thesis Draft", "Sample entry. 96 files, 214 MB."),
    ActivityEntry("Oct 21 · 20:00", "warning", "Schedule", "Thesis Draft backup overdue", "Sample warning. Destination was unavailable at the scheduled time."),
    ActivityEntry("Oct 20 · 18:05", "error", "Verification", "Verification failed for snap-0224 (Lab Reports)", "Sample error. 2 files did not match their recorded checksums. The snapshot would be flagged and not trusted for recovery."),
    ActivityEntry("Oct 20 · 18:02", "info", "Snapshot", "Manual snapshot snap-0224 requested for Lab Reports", "Sample entry."),
    ActivityEntry("Oct 18 · 10:21", "info", "Settings", "Retention policy changed to 30 daily / 12 monthly", "Sample entry."),
    ActivityEntry("Oct 15 · 22:30", "success", "Verification", "Verification passed for snap-0222", "Sample entry. 2,295 files checked."),
    ActivityEntry("Oct 12 · 19:35", "info", "Project", "Protection paused for Math Notes", "Sample entry. Paused by user."),
    ActivityEntry("Oct 12 · 09:00", "info", "App", "SafeFile prototype started", "Sample entry."),
]

_LOCATIONS = [
    StorageLocation("Local Folder", "Local", r"D:\SafeFileBackups", 118.0, 500.0,
                    "Available", "success", "Sample: 3 projects use this location."),
    StorageLocation("External Drive", "External", r"E:\SafeFile", 212.0, 1000.0,
                    "Disconnected", "warning", "Sample: drive not detected. Figures are last known values."),
    StorageLocation("Cloud Storage", "Cloud", "Not configured", 0.0, 0.0,
                    "Planned", "neutral", "Cloud providers (your own accounts) are planned for a later version.",
                    configured=False),
]

_USAGE = [
    ("Video Edit Archive", 142.0),
    ("SafeFile Source", 41.0),
    ("Thesis Draft", 28.0),
    ("Portfolio Website", 14.0),
    ("Lab Reports", 3.0),
    ("Math Notes", 1.0),
]

_MISSING = [
    MissingFile("Chapter 2 - Literature Review.docx", r"C:\Users\Demo\Documents\Thesis", "snap-0225", "284 KB", "snap-0225"),
    MissingFile("old_helpers.py", r"C:\Users\Demo\Projects\safefile\src", "snap-0227", "3.0 KB", "snap-0227"),
    MissingFile("Edit_v5_draft.mp4", r"C:\Users\Demo\Videos\Edits\Exports", "snap-0222", "1.2 GB", "snap-0222"),
]

_CODE_TREE = (
    TreeNode("src", True, children=(
        TreeNode("main.py", size="12.8 KB", modified="Oct 23, 08:12"),
        TreeNode("app.py", size="3.4 KB", modified="Oct 22, 16:40"),
        TreeNode("ui", True, children=(
            TreeNode("sidebar.py", size="6.3 KB", modified="Oct 23, 07:58"),
            TreeNode("dashboard.py", size="9.9 KB", modified="Oct 22, 19:21"),
        )),
    )),
    TreeNode("tests", True, children=(
        TreeNode("test_models.py", size="2.7 KB", modified="Oct 20, 14:05"),
    )),
    TreeNode("README.md", size="2.2 KB", modified="Oct 23, 08:01"),
    TreeNode("requirements.txt", size="0.1 KB", modified="Oct 18, 10:00"),
)

_DOCS_TREE = (
    TreeNode("Chapters", True, children=(
        TreeNode("Chapter 1 - Introduction.docx", size="198 KB", modified="Oct 10, 21:14"),
        TreeNode("Chapter 2 - Literature Review.docx", size="284 KB", modified="Oct 14, 20:48"),
        TreeNode("Chapter 3 - Methods.docx", size="268 KB", modified="Oct 21, 19:55"),
    )),
    TreeNode("Figures", True, children=(
        TreeNode("figure-1.png", size="412 KB", modified="Oct 11, 18:02"),
        TreeNode("figure-2.png", size="388 KB", modified="Oct 11, 18:10"),
    )),
    TreeNode("References.bib", size="18 KB", modified="Oct 21, 19:50"),
)

_SETTINGS = {
    "start_with_windows": True,
    "notifications": True,
    "default_schedule": "Every hour",
    "verify_after_backup": True,
    "retention": "30 daily, 12 monthly",
    "pause_on_battery": False,
    "default_location": r"D:\SafeFileBackups",
    "exclusions": ["node_modules", "__pycache__", "*.tmp", "~$*", "Thumbs.db"],
}


class MockRepository:
    """In-memory sample data implementing `BackupRepository`."""

    def get_overview_stats(self) -> OverviewStats:
        projects = self.get_projects()
        protected = sum(1 for p in projects if p.status_kind == "success")
        attention = sum(1 for p in projects if p.status_kind in ("warning", "error", "info"))
        latest = _SNAPSHOTS[0]
        connected = [l for l in _LOCATIONS if l.configured and l.status_kind == "success"]
        return OverviewStats(
            protected=protected,
            total=len(projects),
            attention=attention,
            latest_snapshot_time=latest.created.split("·")[1].strip(),
            latest_snapshot_caption=f"{latest.created.split('·')[0].strip()} · {latest.project}",
            storage_used_gb=sum(l.used_gb for l in _LOCATIONS),
            connected_locations=len(connected),
        )

    def get_projects(self):
        return list(_PROJECTS)

    def get_snapshots(self):
        return list(_SNAPSHOTS)

    def get_changed_files(self, snapshot_id):
        snap = next((s for s in _SNAPSHOTS if s.id == snapshot_id), None)
        category = "Programming"
        if snap:
            proj = next((p for p in _PROJECTS if p.name == snap.project), None)
            if proj:
                category = proj.category
        return list(_CHANGES.get(category, _CHANGES["Programming"]))

    def get_restore_tree(self, snapshot_id):
        snap = next((s for s in _SNAPSHOTS if s.id == snapshot_id), None)
        proj = next((p for p in _PROJECTS if snap and p.name == snap.project), None)
        if proj and proj.category == "Programming":
            return _CODE_TREE
        return _DOCS_TREE

    def get_missing_files(self):
        return list(_MISSING)

    def get_activity(self):
        return list(_ACTIVITY)

    def get_storage_locations(self):
        return list(_LOCATIONS)

    def get_project_usage(self):
        return list(_USAGE)

    def get_settings(self):
        data = dict(_SETTINGS)
        data["exclusions"] = list(_SETTINGS["exclusions"])
        return data
