"""Projects tab."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit

from safepoint.theme import colors as C
from safepoint.ui.components import Card, create_table, make_button, make_label, populate_table
from safepoint.ui.dialogs import AddProjectDialog, ProjectDialog
from safepoint.ui.screens.base import ScreenBase


class ProjectsScreen(ScreenBase):
    HEADERS = ["Project", "Location", "Back up to", "Schedule", "Last successful backup", "Status"]

    def __init__(self, ctx):
        super().__init__(ctx, "Projects", "Folders SafeFile protects")
        add = make_button("Add project…", "primary")
        add.clicked.connect(self._add)
        self.add_action(add)

        self._projects, self._visible = [], []
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search projects…")
        self.search.setMaximumWidth(320)
        self.status = QComboBox()
        self.status.addItem("All statuses")
        self.count = make_label("", 12, 400, C.MUTED)
        filters.addWidget(self.search)
        filters.addWidget(self.status)
        filters.addStretch()
        filters.addWidget(self.count)
        self.body.addLayout(filters)

        card = Card(padding=8)
        self.table = create_table(self.HEADERS)
        card.body.addWidget(self.table)
        self.body.addWidget(card)
        self.empty = make_label("No projects yet. Use “Add project…” to protect your first folder.", 13, 400, C.MUTED)
        self.body.addWidget(self.empty)

        self.search.textChanged.connect(self._render)
        self.status.currentTextChanged.connect(self._render)
        self.table.cellClicked.connect(self._open)
        self.refresh()

    def refresh(self):
        self._projects = self.repo.get_projects()
        current = self.status.currentText()
        self.status.blockSignals(True)
        self.status.clear()
        self.status.addItem("All statuses")
        self.status.addItems(sorted({p.status_label for p in self._projects}))
        idx = self.status.findText(current)
        self.status.setCurrentIndex(idx if idx >= 0 else 0)
        self.status.blockSignals(False)
        self._render()

    def _render(self, *_):
        text = self.search.text().strip().lower()
        status = self.status.currentText()
        self._visible, rows = [], []
        for p in self._projects:
            if text and text not in p.name.lower() and text not in p.path.lower():
                continue
            if status != "All statuses" and p.status_label != status:
                continue
            self._visible.append(p)
            rows.append([p.name, p.path, p.destination, p.schedule, p.last_ok, (p.status_label, p.status_kind)])
        populate_table(self.table, rows, muted_cols=(1, 2, 3, 4), bold_cols=(0,))
        self.count.setText(f"{len(rows)} of {len(self._projects)} projects")
        self.empty.setVisible(not self._projects)

    def _open(self, row, _col):
        if 0 <= row < len(self._visible):
            ProjectDialog(self.ctx, self._visible[row], self.window()).exec()

    def _add(self):
        if AddProjectDialog(self.ctx, self.window()).exec():
            self.ctx.data_changed.emit()
