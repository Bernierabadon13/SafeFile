"""Restore tab: pick a version, tick files, restore them."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QRadioButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from safepoint.theme import colors as C
from safepoint.ui.components import Card, create_table, make_button, make_label, notice_box, populate_table
from safepoint.ui.dialogs import confirm, folder_row, show_message
from safepoint.ui.screens.base import ScreenBase

_CONFLICTS = [("Keep both files", "keep_both"), ("Skip files that already exist", "skip"),
              ("Overwrite files that already exist", "overwrite")]
_CONFLICT_TEXT = {"keep_both": "kept alongside the restored copy", "skip": "left untouched",
                  "overwrite": "replaced by the restored copy"}


class RecoveryScreen(ScreenBase):
    def __init__(self, ctx):
        super().__init__(ctx, "Restore", "Pick a version, choose files and restore them")
        self._snapshots, self._visible, self._missing = [], [], []
        self._current, self._building, self._leaves = None, False, {}

        columns = QHBoxLayout()
        columns.setSpacing(16)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(16)
        right.setSpacing(16)

        pick = Card("1 · Choose a project and version")
        self.project = QComboBox()
        self.snap_list = QListWidget()
        self.snap_list.setFixedHeight(170)
        self.version_note = notice_box("", "error")
        self.version_note.hide()
        pick.body.addWidget(self.project)
        pick.body.addWidget(self.snap_list)
        pick.body.addWidget(self.version_note)
        left.addWidget(pick)

        files = Card("2 · Select files to recover", "Tick files or whole folders")
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Name", "Size", "Modified"])
        self.tree.setMinimumHeight(300)
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 80)
        self.selected_label = make_label("0 files selected", 12, 400, C.MUTED)
        files.body.addWidget(self.tree)
        files.body.addWidget(self.selected_label)
        left.addWidget(files)

        opts = Card("3 · Restore options")
        self.radio_new = QRadioButton("Restore to a new folder (recommended)")
        self.radio_orig = QRadioButton("Restore to the original location")
        self.radio_new.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.radio_new)
        group.addButton(self.radio_orig)
        self.dest = QLineEdit(str(Path.home() / "Documents" / "SafeFile Restore"))
        self.warn = notice_box("Restoring in place can replace newer files. You will be asked to confirm.", "warning")
        self.warn.hide()
        self.conflict = QComboBox()
        for label, key in _CONFLICTS:
            self.conflict.addItem(label, key)
        self.restore_button = make_button("Restore selected files", "primary", enabled=False)
        self.restore_button.clicked.connect(self._restore)
        opts.body.addWidget(self.radio_new)
        opts.body.addWidget(folder_row(self.window(), self.dest, "Choose where to restore"))
        opts.body.addWidget(self.radio_orig)
        opts.body.addWidget(self.warn)
        opts.body.addWidget(make_label("If a file already exists", 12, 400, C.MUTED))
        opts.body.addWidget(self.conflict)
        opts.body.addSpacing(6)
        opts.body.addWidget(self.restore_button)
        right.addWidget(opts)

        missing = Card("Recently missing files", "Files from your latest backup that are no longer in the folder")
        self.missing_table = create_table(["File", "Folder", "Size"])
        self.missing_empty = make_label("Nothing is missing.", 13, 400, C.MUTED)
        missing.body.addWidget(self.missing_table)
        missing.body.addWidget(self.missing_empty)
        right.addWidget(missing)
        right.addStretch(1)

        columns.addLayout(left, 3)
        columns.addLayout(right, 2)
        self.body.addLayout(columns)

        self.project.currentIndexChanged.connect(lambda _i: self._load_snapshots())
        self.snap_list.currentRowChanged.connect(self._load_tree)
        self.tree.itemChanged.connect(self._update_count)
        self.radio_orig.toggled.connect(self._toggle_dest)
        self.missing_table.cellClicked.connect(self._pick_missing)
        self.refresh()

    # ---------------------------------------------------------------- data
    def refresh(self):
        self._snapshots = self.repo.get_snapshots()
        self._missing = self.repo.get_missing_files()
        keep = self.project.currentData()
        self.project.blockSignals(True)
        self.project.clear()
        seen = set()
        for s in self._snapshots:
            if s.project_id not in seen:
                seen.add(s.project_id)
                self.project.addItem(s.project, s.project_id)
        idx = self.project.findData(keep)
        self.project.setCurrentIndex(idx if idx >= 0 else 0)
        self.project.blockSignals(False)
        self._load_snapshots()
        populate_table(self.missing_table, [[m.name, m.original_path, m.size] for m in self._missing],
                       muted_cols=(1, 2), bold_cols=(0,))
        self.missing_table.setVisible(bool(self._missing))
        self.missing_empty.setVisible(not self._missing)

    def on_show(self):
        self.refresh()
        ctx = self.ctx
        if ctx.pending_snapshot:
            sid, ctx.pending_snapshot = ctx.pending_snapshot, None
            self._select_snapshot(sid)
        elif ctx.pending_project:
            pid, ctx.pending_project = ctx.pending_project, None
            idx = self.project.findData(pid)
            if idx >= 0:
                self.project.setCurrentIndex(idx)

    def _load_snapshots(self, select_id=None):
        pid = self.project.currentData()
        self._visible = [s for s in self._snapshots if s.project_id == pid]
        self.snap_list.blockSignals(True)
        self.snap_list.clear()
        for s in self._visible:
            self.snap_list.addItem(QListWidgetItem(f"{s.id}   ·   {s.created}   ·   {s.verification}"))
        self.snap_list.blockSignals(False)
        row = next((i for i, s in enumerate(self._visible) if s.id == select_id), 0) if self._visible else -1
        self.snap_list.blockSignals(True)
        self.snap_list.setCurrentRow(row)
        self.snap_list.blockSignals(False)
        self._load_tree(row)

    def _select_snapshot(self, snapshot_id):
        snap = next((s for s in self._snapshots if s.id == snapshot_id), None)
        if not snap:
            return
        idx = self.project.findData(snap.project_id)
        if idx >= 0:
            self.project.blockSignals(True)
            self.project.setCurrentIndex(idx)
            self.project.blockSignals(False)
            self._load_snapshots(select_id=snapshot_id)

    def _load_tree(self, row):
        self._building = True
        self.tree.clear()
        self._leaves = {}
        self._current = self._visible[row] if 0 <= row < len(self._visible) else None
        if self._current:
            for node in self.repo.get_restore_tree(self._current.id):
                self._add_node(self.tree.invisibleRootItem(), node)
            self.tree.expandToDepth(0)
            if self._current.verification == "Failed":
                self.version_note.findChild(QLabel).setText(
                    "This version failed verification. Files that are still intact will restore; others will be reported.")
                self.version_note.show()
            else:
                self.version_note.hide()
        else:
            self.version_note.hide()
        self._building = False
        self._update_count()

    def _add_node(self, parent, node):
        item = QTreeWidgetItem(parent, [node.name, node.size, node.modified])
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
        if node.is_folder:
            flags |= Qt.ItemFlag.ItemIsAutoTristate
        item.setFlags(flags)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        if not node.is_folder:
            item.setData(0, Qt.ItemDataRole.UserRole, node.path)
            self._leaves[node.path] = item
        for child in node.children:
            self._add_node(item, child)

    # ---------------------------------------------------------------- selection
    def _checked_paths(self):
        return [p for p, item in self._leaves.items() if item.checkState(0) == Qt.CheckState.Checked]

    def _update_count(self, *_):
        if self._building:
            return
        n = len(self._checked_paths())
        self.selected_label.setText(f"{n} file{'s' if n != 1 else ''} selected")
        self.restore_button.setEnabled(n > 0 and self._current is not None)

    def _toggle_dest(self, original):
        self.warn.setVisible(original)
        self.dest.setEnabled(not original)

    def _pick_missing(self, row, _col):
        if not 0 <= row < len(self._missing):
            return
        m = self._missing[row]
        self._select_snapshot(m.snapshot_id)
        item = self._leaves.get(m.rel_path)
        if item is not None:
            item.setCheckState(0, Qt.CheckState.Checked)
            self.tree.scrollToItem(item)
            self.tree.setCurrentItem(item)

    # ---------------------------------------------------------------- restore
    def _restore(self):
        if not self._current:
            return
        paths = self._checked_paths()
        if not paths:
            return
        conflict = self.conflict.currentData()
        if self.radio_orig.isChecked():
            project = self.repo.get_project(self._current.project_id)
            if project is None:
                return show_message(self.window(), "Project not found", "That project no longer exists.", "error")
            destination = project.path
            if not confirm(self.window(), "Restore into the original folder?",
                           f"{len(paths)} file(s) will be restored into {destination}. Files that already exist "
                           f"there will be {_CONFLICT_TEXT[conflict]}.", "Restore", danger=(conflict == "overwrite")):
                return
        else:
            destination = self.dest.text().strip()
            if not destination:
                return show_message(self.window(), "Choose a folder", "Choose where the files should be restored.")
        self.ctx.restore(self._current.id, paths, destination, conflict, self.window())
