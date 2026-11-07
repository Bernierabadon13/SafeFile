"""Home: backup status, selected folder, last successful backup, Back Up Now."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout

from safepoint.theme import colors as C
from safepoint.ui.components import (
    Card, StatusBadge, clear_layout, list_row, make_button, make_label, notice_box,
)
from safepoint.ui.dialogs import AddProjectDialog
from safepoint.ui.screens.base import ScreenBase


class HomeScreen(ScreenBase):
    def __init__(self, ctx):
        super().__init__(ctx, "Home", "Backup status")
        self.content = None
        self.refresh()

    def refresh(self):
        if self.content is not None:
            clear_layout(self.content)
            self.body.removeItem(self.content)
            self.content.deleteLater()
        self.content = QVBoxLayout()
        self.content.setSpacing(16)
        self.body.addLayout(self.content)

        projects = self.repo.get_projects()
        if not projects:
            card = Card(padding=28)
            card.body.setSpacing(14)
            card.body.addWidget(make_label("No project yet", 22, 600))
            card.body.addWidget(make_label("Choose a folder to start protecting it. Backups are checked after "
                                           "they are made, so you can trust what you see here.", 13, 400, C.MUTED, wrap=True))
            add = make_button("Add Project…", "primary")
            add.clicked.connect(self._add)
            row = QHBoxLayout()
            row.addWidget(add)
            row.addStretch()
            card.body.addLayout(row)
            self.content.addWidget(card)
            return

        selected = self.repo.get_settings().get("selected_project")
        project = next((p for p in projects if p.id == selected), projects[0])

        card = Card(padding=28)
        card.body.setSpacing(16)
        title = QHBoxLayout()
        title.setSpacing(12)
        if len(projects) > 1:
            combo = QComboBox()
            for p in projects:
                combo.addItem(p.name, p.id)
            combo.setCurrentIndex(combo.findData(project.id))
            combo.setMinimumWidth(240)
            combo.activated.connect(lambda i, c=combo: self._select(c.itemData(i)))
            title.addWidget(combo)
        else:
            title.addWidget(make_label(project.name, 22, 600))
        title.addWidget(StatusBadge(project.status_label, project.status_kind))
        title.addStretch()
        card.body.addLayout(title)
        card.body.addWidget(list_row("Selected folder", project.path))
        card.body.addWidget(list_row("Last successful backup", project.last_ok))
        card.body.addWidget(list_row("Back up to", project.destination))
        if project.note:
            kind = project.status_kind if project.status_kind in ("warning", "error") else "info"
            card.body.addWidget(notice_box(project.note, kind))

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        backup = make_button("Back Up Now", "primary")
        backup.clicked.connect(lambda: self.ctx.backup_project(project, self.window()))
        restore = make_button("Restore files", "primary")
        restore.clicked.connect(lambda: self._restore(project))
        buttons.addWidget(backup)
        buttons.addWidget(restore)
        buttons.addStretch()
        card.body.addSpacing(6)
        card.body.addLayout(buttons)
        self.content.addWidget(card)

        attention = [p for p in projects if p.status_kind in ("warning", "error")]
        if attention:
            row = QHBoxLayout()
            row.addWidget(make_label(f"{len(attention)} of {len(projects)} projects need attention", 12, 400, C.MUTED))
            review = make_button("Review in Backups", "link")
            review.clicked.connect(lambda: self.go("projects"))
            row.addWidget(review)
            row.addStretch()
            self.content.addLayout(row)

    def _select(self, project_id):
        self.repo.save_settings({"selected_project": project_id})
        QTimer.singleShot(0, self.refresh)

    def _restore(self, project):
        self.ctx.pending_project = project.id
        self.go("recovery")

    def _add(self):
        if AddProjectDialog(self.ctx, self.window()).exec():
            self.ctx.data_changed.emit()
