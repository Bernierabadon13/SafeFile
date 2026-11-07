"""Dialogs: messages, confirmations, progress, add/edit project, version details, result summaries."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget,
)

from safepoint.config import DESTINATIONS, SCHEDULES
from safepoint.engine.errors import SafeFileError
from safepoint.engine.stores import build_stores, validate_destination
from safepoint.theme import colors as C
from safepoint.ui.components import (
    StatusBadge, create_table, key_value_grid, make_button, make_label, notice_box, populate_table,
)
from safepoint.util import human_size


class DialogBase(QDialog):
    def __init__(self, parent, title, heading, description="", width=560):
        super().__init__(parent)
        self.setWindowTitle(f"{title} — SafeFile")
        self.setModal(True)
        self.setMinimumWidth(width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 20)
        outer.setSpacing(14)
        outer.addWidget(make_label(heading, 18, 600, wrap=True))
        if description:
            outer.addWidget(make_label(description, 13, 400, C.MUTED, wrap=True))
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        outer.addLayout(self.body)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(10)
        self.buttons.addStretch()
        outer.addLayout(self.buttons)

    def add_button(self, text, variant="secondary", handler=None, enabled=True):
        button = make_button(text, variant, enabled=enabled)
        if handler:
            button.clicked.connect(handler)
        self.buttons.addWidget(button)
        return button


def form_grid(rows) -> QWidget:
    holder = QWidget()
    grid = QGridLayout(holder)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(12)
    for i, (label, widget) in enumerate(rows):
        grid.addWidget(make_label(label, 12, 400, C.MUTED), i, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(widget, i, 1)
    grid.setColumnStretch(1, 1)
    return holder


def choose_folder(parent, line_edit: QLineEdit, title="Choose a folder"):
    start = line_edit.text().strip() or str(Path.home())
    folder = QFileDialog.getExistingDirectory(parent, title, start)
    if folder:
        line_edit.setText(os.path.normpath(folder))
        return True
    return False


def folder_row(parent, line_edit: QLineEdit, title="Choose a folder") -> QWidget:
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    row.addWidget(line_edit, 1)
    button = make_button("Choose Folder…", "primary")
    button.clicked.connect(lambda: choose_folder(parent, line_edit, title))
    row.addWidget(button)
    return holder


# ------------------------------------------------------------------ simple dialogs
def show_message(parent, heading, text, kind="info", details=""):
    dlg = DialogBase(parent, "SafeFile", heading, width=520)
    if kind == "info":
        dlg.body.addWidget(make_label(text, 13, wrap=True))
    else:
        dlg.body.addWidget(notice_box(text, kind))
    if details:
        box = QPlainTextEdit(details)
        box.setReadOnly(True)
        box.setFixedHeight(140)
        dlg.body.addWidget(box)
    ok = dlg.add_button("OK", "primary", dlg.accept)
    ok.setDefault(True)
    dlg.exec()


def confirm(parent, heading, text, action_text, danger=False) -> bool:
    dlg = DialogBase(parent, "Confirm", heading, width=520)
    dlg.body.addWidget(make_label(text, 13, wrap=True))
    cancel = dlg.add_button("Cancel", handler=dlg.reject)
    dlg.add_button(action_text, "danger" if danger else "primary", dlg.accept)
    cancel.setDefault(True)
    return dlg.exec() == QDialog.DialogCode.Accepted


class ProgressDialog(DialogBase):
    """Shows real progress reported by the engine. Closing or Cancel asks the task to stop."""

    def __init__(self, parent, heading, cancel_event):
        super().__init__(parent, "Working", heading, width=540)
        self._cancel_event = cancel_event
        self._finished = False
        self.stage = make_label("Starting…", 13)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.detail = make_label("", 12, 400, C.MUTED)
        for w in (self.stage, self.bar, self.detail):
            self.body.addWidget(w)
        self.cancel_button = self.add_button("Cancel", handler=self._cancel)

    def update_progress(self, stage, done, total, detail):
        if self._cancel_event.is_set():
            return
        if total and total > 0:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(min(1.0, done / total) * 1000))
            self.stage.setText(f"{stage}  ·  {int(min(1.0, done / total) * 100)}%")
        else:
            self.bar.setRange(0, 0)
            self.stage.setText(stage)
        self.detail.setText(self.detail.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideMiddle, 480))

    def _cancel(self):
        self._cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.stage.setText("Cancelling…")

    def reject(self):
        self._cancel()

    def closeEvent(self, event):  # noqa: N802
        if self._finished:
            event.accept()
        else:
            self._cancel()
            event.ignore()

    def finish(self):
        self._finished = True
        self.accept()


# ------------------------------------------------------------------ result summaries
def show_backup_result(parent, name, r):
    where = ", ".join(r.destinations) or "the destination"
    details = "\n".join(f"{p}: {why}" for p, why in r.skipped)
    if r.status == "unchanged":
        show_message(parent, "Nothing new to back up", f"{name} has not changed since the last backup.", "info", details)
    elif r.status == "verified":
        text = (f"{r.files:,} files ({human_size(r.total_bytes)}) saved as {r.snapshot_id} to {where} "
                f"and checked against their fingerprints. {human_size(r.uploaded_bytes)} of new data was copied.")
        if r.skipped:
            text += f" {len(r.skipped)} file(s) could not be included (see details)."
        show_message(parent, "Backup complete and verified", text, "warning" if r.skipped else "success", details)
    elif r.status == "failed":
        show_message(parent, "Backup saved, but verification failed", r.message, "error", details)
    else:
        show_message(parent, "Backup saved, but not verified yet", r.message, "warning", details)


def show_verify_result(parent, snapshot_id, v):
    if v.state == "verified":
        show_message(parent, "Version verified", f"{snapshot_id} was read back and every file matches its fingerprint.", "success")
    elif v.state == "failed":
        show_message(parent, "Verification failed", f"{snapshot_id} has problems. Do not rely on it for recovery.",
                     "error", "\n".join(v.problems))
    else:
        show_message(parent, "Could not finish verifying",
                     "Some destinations were not reachable, so this version is still unverified.", "warning",
                     "\n".join(v.unreachable))


def show_restore_result(parent, r):
    details = "\n".join(f"{p}: {why}" for p, why in r.failed)
    extra = f" {r.skipped_existing} existing file(s) were left untouched." if r.skipped_existing else ""
    if r.failed and r.restored:
        show_message(parent, "Restore finished with problems",
                     f"{r.restored} file(s) restored to {r.destination}; {len(r.failed)} could not be restored.{extra}",
                     "warning", details)
    elif r.failed:
        show_message(parent, "Restore failed", f"No files could be restored to {r.destination}.", "error", details)
    else:
        show_message(parent, "Restore complete",
                     f"{r.restored} file(s) ({human_size(r.bytes_written)}) restored to {r.destination}. "
                     f"Each file was checked against its fingerprint.{extra}", "success")


# ------------------------------------------------------------------ add / edit project
def _schedule_combo(current=None):
    box = QComboBox()
    box.addItems(list(SCHEDULES))
    if current:
        box.setCurrentText(current)
    return box


def _destination_combo(current=None):
    box = QComboBox()
    for key, label in DESTINATIONS.items():
        box.addItem(label, key)
    if current:
        box.setCurrentIndex(max(0, box.findData(current)))
    return box


class AddProjectDialog(DialogBase):
    def __init__(self, ctx, parent=None):
        super().__init__(parent, "Add project", "Add a project to protect",
                         "Choose the folder SafeFile should back up.", width=640)
        self.ctx = ctx
        settings = ctx.repo.get_settings()
        self.path = QLineEdit()
        self.path.setPlaceholderText(r"C:\Users\You\Documents\MyProject")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Project name")
        self.dest = _destination_combo("local")
        self.schedule = _schedule_combo(settings["default_schedule"])
        self.skip = QLineEdit(", ".join(settings["default_exclusions"]))
        self.error = notice_box("", "error")
        self.error.hide()
        self._error_label = self.error.findChild(QLabel)
        self.body.addWidget(form_grid([
            ("Folder to protect", folder_row(self, self.path, "Choose the folder to protect")),
            ("Project name", self.name),
            ("Back up to", self.dest),
            ("Automatic backup", self.schedule),
            ("Skip files matching", self.skip),
        ]))
        self.body.addWidget(self.error)
        self.path.editingFinished.connect(self._suggest_name)
        self.add_button("Cancel", handler=self.reject)
        self.add_button("Add project", "primary", self._submit)

    def _suggest_name(self):
        if not self.name.text().strip() and self.path.text().strip():
            self.name.setText(Path(self.path.text().strip()).name)

    def _fail(self, text):
        self._error_label.setText(text)
        self.error.show()

    def _submit(self):
        self._suggest_name()
        name, path = self.name.text().strip(), os.path.normpath(self.path.text().strip() or ".")
        if not self.path.text().strip() or not os.path.isdir(path):
            return self._fail("Choose a folder that exists.")
        if not name:
            return self._fail("Enter a project name.")
        destination = self.dest.currentData()
        try:
            for store in build_stores(self.ctx.repo.get_settings(), destination):
                validate_destination(path, store)
        except SafeFileError as err:
            return self._fail(str(err))
        patterns = [p.strip() for p in self.skip.text().split(",") if p.strip()]
        project_id = self.ctx.repo.add_project(name, path, destination, self.schedule.currentText(), patterns)
        self.ctx.repo.save_settings({"selected_project": str(project_id)})
        self.accept()


class ProjectDialog(DialogBase):
    def __init__(self, ctx, project, parent=None):
        super().__init__(parent, "Project", project.name, project.path, width=620)
        self.ctx, self.project = ctx, project
        self.schedule = _schedule_combo(project.schedule)
        self.dest = _destination_combo(project.destination_key)
        self.paused = QCheckBox("Pause automatic backups")
        self.paused.setChecked(project.paused)
        self.body.addWidget(key_value_grid([
            ("Status", StatusBadge(project.status_label, project.status_kind)),
            ("Last successful backup", project.last_ok),
            ("Latest version", f"{project.last_snapshot} · {project.file_count:,} files · {project.size}"),
        ], label_width=170))
        if project.note and project.status_kind in ("warning", "error"):
            self.body.addWidget(notice_box(project.note, project.status_kind))
        self.body.addWidget(form_grid([("Back up to", self.dest), ("Automatic backup", self.schedule), ("", self.paused)]))
        remove = make_button("Remove project", "danger")
        remove.clicked.connect(self._remove)
        self.buttons.insertWidget(0, remove)
        self.add_button("Close", handler=self.reject)
        self.add_button("Save changes", handler=self._save)
        self.add_button("Back Up Now", "primary", self._backup)

    def _save(self):
        self.ctx.repo.update_project(self.project.id, schedule=self.schedule.currentText(),
                                     destination=self.dest.currentData(), paused=self.paused.isChecked())
        self.ctx.data_changed.emit()
        self.accept()

    def _backup(self):
        self.accept()
        self.ctx.backup_project(self.project, self.parent())

    def _remove(self):
        if confirm(self, "Remove this project?",
                   f"SafeFile will stop protecting {self.project.name} and delete its version history. "
                   "Your original files are not touched. Backup data that no other version uses is deleted "
                   "from the destinations.", "Remove project", danger=True):
            self.accept()
            self.ctx.remove_project(self.project, self.parent())


class SnapshotDialog(DialogBase):
    def __init__(self, ctx, snapshot, changes, on_restore, parent=None):
        super().__init__(parent, "Version", f"Version {snapshot.id}", f"{snapshot.project} · {snapshot.created}", width=680)
        self.ctx, self.snapshot, self._on_restore = ctx, snapshot, on_restore
        table = create_table(["Change", "File", "Size"], stretch_col=1)
        kinds = {"Added": "success", "Modified": "info", "Removed": "error"}
        populate_table(table, [[(c.change, kinds.get(c.change, "neutral")), c.path, c.size] for c in changes[:12]],
                       muted_cols=(2,))
        table.setStyleSheet(f"QTableWidget {{ border: 1px solid {C.BORDER}; border-radius: 8px; }}")
        pairs = [
            ("Type", snapshot.kind),
            ("Files", f"{snapshot.files:,} files · {snapshot.size}"),
            ("Changes", f"+{snapshot.added} added · {snapshot.modified} modified · {snapshot.removed} removed"),
            ("Verification", StatusBadge(snapshot.verification, snapshot.verification_kind)),
        ]
        if snapshot.note:
            pairs.append(("Note", snapshot.note))
        self.body.addWidget(key_value_grid(pairs))
        if snapshot.detail:
            self.body.addWidget(notice_box(snapshot.detail, "error"))
        if changes:
            more = f" (first 12 of {len(changes)})" if len(changes) > 12 else ""
            self.body.addWidget(make_label(f"Changes since the previous version{more}", 12, 400, C.MUTED))
            self.body.addWidget(table)
        self.add_button("Close", handler=self.reject)
        self.add_button("Verify now", handler=self._verify)
        self.add_button("Restore from this version", "primary", self._restore)

    def _verify(self):
        self.accept()
        self.ctx.verify_snapshot(self.snapshot.id, self.parent())

    def _restore(self):
        self.accept()
        self._on_restore(self.snapshot.id)


# ------------------------------------------------------------------ quick saves (drag and drop)
def summarize_quick(results):
    """results: [(path, BackupResult | None, error | None)] -> (level, headline, lines)."""
    good, bad = [], []
    for path, r, err in results:
        name = os.path.basename(path.rstrip("\\/")) or path
        if err:
            bad.append(f"{name}: {err}")
        elif r.status in ("verified", "unchanged"):
            good.append(f"{name}: saved as {r.snapshot_id} and verified")
        else:
            bad.append(f"{name}: {r.message}")
    if bad and good:
        return "warning", "Saved with problems", good + bad
    if bad:
        return "error", "Could not save", bad
    return "success", ("Version saved and verified" if len(good) == 1 else f"{len(good)} versions saved and verified"), good


def show_quick_results(parent, results):
    level, headline, lines = summarize_quick(results)
    show_message(parent, headline, lines[0] if len(lines) == 1 else f"{len(lines)} items processed.", level,
                 "" if len(lines) == 1 else "\n".join(lines))


def ask_note(parent, heading="Save a new version") -> tuple:
    """Returns (accepted, note)."""
    dlg = DialogBase(parent, "New version", heading, "Add a short note so you can find this version later (optional).",
                     width=480)
    note = QLineEdit()
    note.setPlaceholderText("What changed?")
    dlg.body.addWidget(note)
    dlg.add_button("Cancel", handler=dlg.reject)
    save = dlg.add_button("Save version", "primary", dlg.accept)
    save.setDefault(True)
    note.returnPressed.connect(dlg.accept)
    ok = dlg.exec() == QDialog.DialogCode.Accepted
    return ok, note.text().strip()


class RestoreVersionDialog(DialogBase):
    """Restore one saved version of a quick-save item."""

    def __init__(self, ctx, snapshot, item, parent=None):
        super().__init__(parent, "Restore", f"Restore {snapshot.id}", f"{item.name} · saved {snapshot.created}", width=600)
        self.ctx, self.snapshot, self.item = ctx, snapshot, item
        self.dest = QLineEdit(str(Path.home() / "Documents" / "SafeFile Restore"))
        self.original = QCheckBox("Put it back where it came from (replaces the current file)")
        self.original.toggled.connect(lambda on: self.dest.setEnabled(not on))
        self.body.addWidget(form_grid([("Restore to", folder_row(self, self.dest, "Choose where to restore")),
                                       ("", self.original)]))
        self.add_button("Cancel", handler=self.reject)
        self.add_button("Restore", "primary", self._restore)

    def _restore(self):
        paths = self.ctx.repo.get_snapshot_paths(self.snapshot.id)
        if self.original.isChecked():
            target = self.item.path if self.item.is_folder else os.path.dirname(self.item.path)
            if not confirm(self, "Replace the current version?",
                           f"The current {'folder contents' if self.item.is_folder else 'file'} will be replaced by "
                           f"{self.snapshot.id}. Save a new version first if you may need the current one.",
                           "Replace", danger=True):
                return
            conflict = "overwrite"
        else:
            target = self.dest.text().strip()
            if not target:
                return show_message(self, "Choose a folder", "Choose where the files should be restored.")
            conflict = "keep_both"
        self.accept()
        self.ctx.restore(self.snapshot.id, paths, target, conflict, self.parent())


class QuickItemDialog(DialogBase):
    """Everything about one dropped file or folder: its own list of versions."""

    def __init__(self, ctx, item, parent=None):
        super().__init__(parent, "Quick save", item.name, item.path, width=780)
        self.ctx, self.item, self._versions, self._selected = ctx, item, [], None
        self.status = StatusBadge(item.status_label, item.status_kind)
        self.table = create_table(["Version", "Saved", "Size", "Note", "Verification"], stretch_col=3)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setFixedHeight(280)
        self.table.cellClicked.connect(self._pick)
        self.empty = make_label("No versions yet.", 13, 400, C.MUTED)
        self.body.addWidget(self.status)
        self.body.addWidget(self.table)
        self.body.addWidget(self.empty)
        self.body.addWidget(make_label(
            "Every save is its own version, even if the content is the same. Versions of a quick-save item are kept "
            "until you remove the item.", 12, 400, C.MUTED, wrap=True))
        self.remove_button = make_button("Remove item", "danger")
        self.remove_button.clicked.connect(self._remove)
        self.buttons.insertWidget(0, self.remove_button)
        self.add_button("Close", handler=self.reject)
        self.restore_button = self.add_button("Restore selected version…", handler=self._restore, enabled=False)
        self.save_button = self.add_button("Save new version", "primary", self._save)
        ctx.data_changed.connect(self._reload)
        self._reload()

    def _reload(self):
        item = self.ctx.repo.get_quick_item(self.item.id)
        if item is None:
            self.accept()
            return
        self.item = item
        self._versions = self.ctx.repo.get_item_snapshots(item.id)
        rows = [[s.id, s.created, s.size, s.note or "—", (s.verification, s.verification_kind)] for s in self._versions]
        populate_table(self.table, rows, muted_cols=(1, 2, 3), bold_cols=(0,), fit=False)
        self.table.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        self.save_button.setEnabled(item.exists)
        self.save_button.setToolTip("" if item.exists else "The original is missing, so there is nothing to save.")
        if rows:
            self.table.selectRow(0)
            self._selected = self._versions[0]
        else:
            self._selected = None
        self.restore_button.setEnabled(self._selected is not None)

    def _pick(self, row, _col):
        if 0 <= row < len(self._versions):
            self._selected = self._versions[row]
            self.restore_button.setEnabled(True)

    def _save(self):
        ok, note = ask_note(self)
        if ok:
            self.ctx.quick_save([self.item.path], self.item.destination_key, self, note=note)

    def _restore(self):
        if self._selected:
            RestoreVersionDialog(self.ctx, self._selected, self.item, self).exec()

    def _remove(self):
        if confirm(self, "Remove this item?",
                   f"SafeFile will forget {self.item.name} and delete all of its saved versions. The original is not "
                   "touched. Backup data that nothing else uses is deleted from the destinations.",
                   "Remove item", danger=True):
            self.accept()
            self.ctx.remove_project(self.item, self.parent())
