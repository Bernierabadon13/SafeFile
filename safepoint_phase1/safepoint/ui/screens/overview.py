"""Overview dashboard."""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout

from safepoint.theme import colors as C
from safepoint.ui.components import (
    Card, StatusBadge, StatusDot, StorageBar, SummaryCard, list_row, make_button, make_label,
)
from safepoint.ui.dialogs import show_add_project, show_backup_now, show_verify_preview
from safepoint.ui.screens.base import ScreenBase


class OverviewScreen(ScreenBase):
    def __init__(self, repo):
        super().__init__(repo, "Overview", "Protection status across your projects (sample data)")
        backup = make_button("Back up now…", "primary")
        backup.clicked.connect(lambda: show_backup_now(self.window()))
        self.add_action(backup)

        stats = repo.get_overview_stats()
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(SummaryCard("Protected projects", f"{stats.protected} of {stats.total}",
                                  "Projects whose latest sample snapshot is marked verified", "success"))
        row.addWidget(SummaryCard("Needs attention", str(stats.attention),
                                  "Overdue, failed or unverified (sample)", "warning"))
        row.addWidget(SummaryCard("Latest snapshot", stats.latest_snapshot_time,
                                  stats.latest_snapshot_caption, "info"))
        row.addWidget(SummaryCard("Storage used", f"{stats.storage_used_gb:.0f} GB",
                                  f"{stats.connected_locations} location connected (sample)", "info"))
        self.body.addLayout(row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.addWidget(self._projects_card(), 0, 0)
        grid.addWidget(self._storage_card(), 0, 1)
        grid.addWidget(self._activity_card(), 1, 0)
        grid.addWidget(self._actions_card(), 1, 1)
        self.body.addLayout(grid)

    def _projects_card(self):
        link = make_button("View all", "link")
        link.clicked.connect(lambda: self.go("projects"))
        card = Card("Protected projects", "Status shown is sample data", link)
        for p in self.repo.get_projects():
            card.body.addWidget(list_row(p.name, f"{p.destination} · {p.last_snapshot}",
                                         StatusBadge(p.status_label, p.status_kind)))
        return card

    def _storage_card(self):
        link = make_button("Manage", "link")
        link.clicked.connect(lambda: self.go("storage"))
        card = Card("Storage", "Backup destinations (sample)", link)
        for loc in self.repo.get_storage_locations():
            top = QHBoxLayout()
            top.addWidget(make_label(loc.name, 13, 600))
            top.addStretch()
            if loc.configured:
                top.addWidget(make_label(f"{loc.used_gb:.0f} / {loc.total_gb:.0f} GB", 12, 400, C.MUTED))
            else:
                top.addWidget(StatusBadge(loc.status, loc.status_kind))
            card.body.addLayout(top)
            if loc.configured:
                card.body.addWidget(StorageBar([(loc.used_gb / loc.total_gb, C.ACCENT)]))
                if loc.status_kind != "success":
                    card.body.addWidget(make_label(loc.status, 12, 400, C.WARNING_TEXT))
            card.body.addSpacing(6)
        return card

    def _activity_card(self):
        link = make_button("View logs", "link")
        link.clicked.connect(lambda: self.go("logs"))
        card = Card("Recent activity", "Sample log entries", link)
        for entry in self.repo.get_activity()[:6]:
            card.body.addWidget(list_row(entry.message, entry.time, left=StatusDot(entry.level)))
        return card

    def _actions_card(self):
        card = Card("Quick actions")
        add = make_button("Add project…", "primary")
        add.clicked.connect(lambda: show_add_project(self.window()))
        rec = make_button("Open Recovery Center")
        rec.clicked.connect(lambda: self.go("recovery"))
        hist = make_button("Review backup history")
        hist.clicked.connect(lambda: self.go("history"))
        ver = make_button("Verify latest snapshot…")
        ver.clicked.connect(lambda: show_verify_preview(self.window(), "snap-0231"))
        for b in (add, rec, hist, ver):
            card.body.addWidget(b)
        card.body.addSpacing(6)
        card.body.addWidget(make_label(
            "Phase 1 is a static interface. Buttons open previews or move between screens; "
            "nothing is backed up, verified or restored.", 12, 400, C.MUTED, wrap=True))
        return card
