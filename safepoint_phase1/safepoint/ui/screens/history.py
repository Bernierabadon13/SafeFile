"""Version history tab."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout

from safepoint.theme import colors as C
from safepoint.ui.components import Card, create_table, make_button, make_label, populate_table
from safepoint.ui.dialogs import SnapshotDialog
from safepoint.ui.screens.base import ScreenBase


class HistoryScreen(ScreenBase):
    HEADERS = ["Version", "Project", "Created", "Type", "Changes", "Size", "Verification"]

    def __init__(self, ctx):
        super().__init__(ctx, "Version history", "Every saved version of your projects")
        recover = make_button("Restore files", "primary")
        recover.clicked.connect(lambda: self.go("recovery"))
        self.add_action(recover)

        self._snapshots, self._visible = [], []
        filters = QHBoxLayout()
        self.project = QComboBox()
        self.verification = QComboBox()
        self.verification.addItems(["All verification states", "Verified", "Pending", "Failed"])
        self.count = make_label("", 12, 400, C.MUTED)
        filters.addWidget(self.project)
        filters.addWidget(self.verification)
        filters.addStretch()
        filters.addWidget(self.count)
        self.body.addLayout(filters)

        card = Card(padding=8)
        self.table = create_table(self.HEADERS, stretch_col=1)
        card.body.addWidget(self.table)
        self.body.addWidget(card)
        self.empty = make_label("No versions yet. They appear here after your first backup.", 13, 400, C.MUTED)
        self.body.addWidget(self.empty)

        self.project.currentTextChanged.connect(self._render)
        self.verification.currentTextChanged.connect(self._render)
        self.table.cellClicked.connect(self._open)
        self.refresh()

    def refresh(self):
        self._snapshots = self.repo.get_snapshots()
        current = self.project.currentText()
        self.project.blockSignals(True)
        self.project.clear()
        self.project.addItem("All projects")
        self.project.addItems(sorted({s.project for s in self._snapshots}))
        idx = self.project.findText(current)
        self.project.setCurrentIndex(idx if idx >= 0 else 0)
        self.project.blockSignals(False)
        self._render()

    def _render(self, *_):
        proj, ver = self.project.currentText(), self.verification.currentText()
        self._visible, rows = [], []
        for s in self._snapshots:
            if proj != "All projects" and s.project != proj:
                continue
            if ver != "All verification states" and s.verification != ver:
                continue
            self._visible.append(s)
            rows.append([s.id, s.project, s.created, s.kind, f"+{s.added}   ~{s.modified}   −{s.removed}",
                         s.size, (s.verification, s.verification_kind)])
        populate_table(self.table, rows, muted_cols=(2, 3, 4, 5), bold_cols=(0,))
        self.count.setText(f"{len(rows)} of {len(self._snapshots)} versions")
        self.empty.setVisible(not self._snapshots)

    def _open(self, row, _col):
        if 0 <= row < len(self._visible):
            snap = self._visible[row]
            SnapshotDialog(self.ctx, snap, self.repo.get_changed_files(snap.id), self._restore, self.window()).exec()

    def _restore(self, snapshot_id):
        self.ctx.pending_snapshot = snapshot_id
        self.go("recovery")
