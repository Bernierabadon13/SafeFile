"""Activity Logs screen."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit

from safepoint.theme import colors as C
from safepoint.ui.components import Card, create_table, make_button, make_label, populate_table
from safepoint.ui.dialogs import show_export_logs, show_log_details
from safepoint.ui.screens.base import ScreenBase


class LogsScreen(ScreenBase):
    HEADERS = ["Time (sample)", "Level", "Category", "Message"]

    def __init__(self, repo):
        super().__init__(repo, "Activity Logs", "Sample event records")
        export = make_button("Export log…")
        export.clicked.connect(lambda: show_export_logs(self.window()))
        self.add_action(export)

        self._entries = repo.get_activity()
        self._visible = []

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search messages…")
        self.search.setMaximumWidth(320)
        self.level = QComboBox()
        self.level.addItems(["All levels", "Info", "Success", "Warning", "Error"])
        self.category = QComboBox()
        self.category.addItem("All categories")
        self.category.addItems(sorted({e.category for e in self._entries}))
        self.count = make_label("", 12, 400, C.MUTED)
        for w in (self.search, self.level, self.category):
            filters.addWidget(w)
        filters.addStretch()
        filters.addWidget(self.count)
        self.body.addLayout(filters)

        card = Card(padding=8)
        self.table = create_table(self.HEADERS, stretch_col=3)
        card.body.addWidget(self.table)
        self.body.addWidget(card)
        self.body.addWidget(make_label("Select a row to preview the full entry.", 12, 400, C.MUTED))

        self.search.textChanged.connect(self._refresh)
        self.level.currentTextChanged.connect(self._refresh)
        self.category.currentTextChanged.connect(self._refresh)
        self.table.cellClicked.connect(self._open)
        self._refresh()

    def _refresh(self, *_):
        text = self.search.text().strip().lower()
        level = self.level.currentText().lower()
        category = self.category.currentText()
        self._visible = []
        rows = []
        for e in self._entries:
            if text and text not in e.message.lower():
                continue
            if level != "all levels" and e.level != level:
                continue
            if category != "All categories" and e.category != category:
                continue
            self._visible.append(e)
            rows.append([e.time, (e.level.title(), e.level), e.category, e.message])
        populate_table(self.table, rows, muted_cols=(0, 2))
        self.count.setText(f"{len(rows)} of {len(self._entries)} entries")

    def _open(self, row, _col):
        if 0 <= row < len(self._visible):
            show_log_details(self.window(), self._visible[row])
