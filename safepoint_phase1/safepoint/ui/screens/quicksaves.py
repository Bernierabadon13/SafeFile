"""Quick saves tab: files and folders saved on demand, each with its own history."""
from __future__ import annotations

import os

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout

from safepoint.config import DESTINATIONS
from safepoint.theme import colors as C
from safepoint.ui.components import Card, create_table, make_button, make_label, populate_table
from safepoint.ui.dialogs import QuickItemDialog
from safepoint.ui.screens.base import ScreenBase


class QuickSavesScreen(ScreenBase):
    HEADERS = ["Item", "Location", "Versions", "Last saved", "Status"]

    def __init__(self, ctx):
        super().__init__(ctx, "Quick saves", "Save a file or folder whenever you want. Each one keeps its own history.")
        add_file = make_button("Add files…", "primary")
        add_file.clicked.connect(self._add_files)
        add_folder = make_button("Add folder…", "primary")
        add_folder.clicked.connect(self._add_folder)
        drop = make_button("Open drop window")
        drop.clicked.connect(lambda: self.go("dropwindow"))
        for b in (drop, add_folder, add_file):
            self.add_action(b)

        self._items = []
        row = QHBoxLayout()
        row.addWidget(make_label("Save to", 12, 400, C.MUTED))
        self.dest = QComboBox()
        for key, label in DESTINATIONS.items():
            self.dest.addItem(label, key)
        self.dest.setCurrentIndex(max(0, self.dest.findData(self.repo.get_settings().get("quick_destination", "local"))))
        row.addWidget(self.dest)
        row.addStretch()
        self.count = make_label("", 12, 400, C.MUTED)
        row.addWidget(self.count)
        self.body.addLayout(row)

        card = Card(padding=8)
        self.table = create_table(self.HEADERS, stretch_col=1)
        card.body.addWidget(self.table)
        self.body.addWidget(card)
        self.empty = make_label(
            "Nothing saved yet. Drop files on the drop window, or use “Add files…” and “Add folder…”.",
            13, 400, C.MUTED, wrap=True)
        self.body.addWidget(self.empty)
        self.table.cellClicked.connect(self._open)
        self.refresh()

    def refresh(self):
        self._items = self.repo.get_quick_items()
        populate_table(self.table, [[i.name, i.path, str(i.versions), i.last_saved, (i.status_label, i.status_kind)]
                                    for i in self._items], muted_cols=(1, 2, 3), bold_cols=(0,))
        self.count.setText(f"{len(self._items)} item{'s' if len(self._items) != 1 else ''}")
        self.empty.setVisible(not self._items)

    def _open(self, row, _col):
        if 0 <= row < len(self._items):
            QuickItemDialog(self.ctx, self._items[row], self.window()).exec()

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self.window(), "Choose files to save")
        if paths:
            self.ctx.quick_save(paths, self.dest.currentData(), self.window())

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self.window(), "Choose a folder to save")
        if folder:
            self.ctx.quick_save([os.path.normpath(folder)], self.dest.currentData(), self.window())
