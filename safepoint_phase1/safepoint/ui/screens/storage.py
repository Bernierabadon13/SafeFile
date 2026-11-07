"""Storage screen."""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout

from safepoint.theme import colors as C
from safepoint.ui.components import (
    Card, StatusBadge, StorageBar, key_value_grid, make_button, make_label, notice_box,
)
from safepoint.ui.dialogs import show_change_location
from safepoint.ui.screens.base import ScreenBase

_PALETTE = C.BAR_PALETTE


class StorageScreen(ScreenBase):
    def __init__(self, repo):
        super().__init__(repo, "Storage", "Backup destinations and space usage (sample data)")
        change = make_button("Change backup location…", "primary")
        change.clicked.connect(lambda: show_change_location(self.window()))
        self.add_action(change)

        locations = repo.get_storage_locations()
        if any(l.status_kind == "warning" for l in locations):
            self.body.addWidget(notice_box(
                "Sample warning: the external drive is shown as disconnected. Projects using it would be "
                "marked overdue until it returns.", "warning"))

        row = QHBoxLayout()
        row.setSpacing(16)
        for loc in locations:
            row.addWidget(self._location_card(loc))
        self.body.addLayout(row)

        lower = QGridLayout()
        lower.setHorizontalSpacing(16)
        lower.setColumnStretch(0, 3)
        lower.setColumnStretch(1, 2)
        lower.addWidget(self._usage_card(), 0, 0)
        lower.addWidget(self._retention_card(), 0, 1)
        self.body.addLayout(lower)

    def _location_card(self, loc):
        card = Card()
        top = QHBoxLayout()
        top.addWidget(make_label(loc.name, 15, 600))
        top.addStretch()
        top.addWidget(StatusBadge(loc.status, loc.status_kind))
        card.body.addLayout(top)
        card.body.addWidget(make_label(loc.path, 12, 400, C.MUTED, wrap=True))
        if loc.configured:
            bar_color = C.ACCENT if loc.status_kind == "success" else C.KIND_COLORS["neutral"]
            card.body.addSpacing(4)
            card.body.addWidget(StorageBar([(loc.used_gb / loc.total_gb, bar_color)], height=12))
            free = loc.total_gb - loc.used_gb
            card.body.addWidget(make_label(f"{loc.used_gb:.0f} GB used of {loc.total_gb:.0f} GB", 13, 600))
            card.body.addWidget(make_label(f"{free:.0f} GB free (sample)", 12, 400, C.MUTED))
        card.body.addWidget(make_label(loc.note, 12, 400, C.MUTED, wrap=True))
        return card

    def _usage_card(self):
        card = Card("Usage by project", "Approximate space per project (sample)")
        usage = self.repo.get_project_usage()
        top = max(gb for _n, gb in usage)
        for i, (name, gb) in enumerate(usage):
            line = QHBoxLayout()
            line.addWidget(make_label(name, 13, 600))
            line.addStretch()
            line.addWidget(make_label(f"{gb:.0f} GB", 12, 400, C.MUTED))
            card.body.addLayout(line)
            card.body.addWidget(StorageBar([(gb / top, _PALETTE[i % len(_PALETTE)])]))
            card.body.addSpacing(4)
        return card

    def _retention_card(self):
        card = Card("Retention and efficiency", "Illustrative values")
        card.body.addWidget(key_value_grid([
            ("Snapshots listed", "11 (sample)"),
            ("Retention policy", "30 daily, 12 monthly"),
            ("Space savings", "About 38% (sample)"),
            ("Next cleanup", "Not scheduled"),
        ], label_width=130))
        card.body.addWidget(make_label(
            "Cleanup of old snapshots is not part of this prototype.", 12, 400, C.MUTED, wrap=True))
        return card
