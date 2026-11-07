"""Small always-on-top window: drop files or folders to save a new version of each."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from safepoint.config import DESTINATIONS
from safepoint.theme import colors as C
from safepoint.ui.components import make_app_icon, make_button, make_label
from safepoint.ui.dialogs import show_message, summarize_quick


class DropWindow(QWidget):
    def __init__(self, ctx, open_main):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.ctx = ctx
        self._open_main = open_main
        self.setObjectName("DropWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("SafeFile — Quick save")
        self.setWindowIcon(make_app_icon())
        self.setAcceptDrops(True)
        self.resize(340, 330)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self.zone = QFrame()
        self.zone.setObjectName("DropZone")
        self.zone.setProperty("dragging", False)
        zone_layout = QVBoxLayout(self.zone)
        zone_layout.setContentsMargins(16, 28, 16, 28)
        zone_layout.setSpacing(6)
        zone_layout.addWidget(make_label("Drop files or folders here", 15, 600, align=Qt.AlignmentFlag.AlignCenter))
        zone_layout.addWidget(make_label("Each drop saves a new version of every item.", 12, 400, C.MUTED,
                                         wrap=True, align=Qt.AlignmentFlag.AlignCenter))
        layout.addWidget(self.zone, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(make_label("Save to", 12, 400, C.MUTED))
        self.dest = QComboBox()
        for key, label in DESTINATIONS.items():
            self.dest.addItem(label, key)
        self.dest.setCurrentIndex(max(0, self.dest.findData(ctx.repo.get_settings().get("quick_destination", "local"))))
        row.addWidget(self.dest, 1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        choose = make_button("Choose files…")
        choose.clicked.connect(self._choose)
        main = make_button("Open SafeFile", "link")
        main.clicked.connect(lambda: self._open_main("quick"))
        buttons.addWidget(choose)
        buttons.addWidget(main)
        layout.addLayout(buttons)

        self.status = make_label("Ready.", 12, 400, C.MUTED, wrap=True)
        layout.addWidget(self.status)
        ctx.activity.connect(self._activity)

    # ---------------------------------------------------------------- status
    def _set_status(self, text, kind="muted"):
        color = {"muted": C.MUTED, "success": C.SUCCESS, "warning": C.WARNING_TEXT, "error": C.ERROR_TEXT}[kind]
        self.status.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        self.status.setText(text)

    def _activity(self, text):
        if text != "Idle" and self.isVisible():
            self._set_status(text)

    # ---------------------------------------------------------------- drag and drop
    def _dragging(self, on):
        self.zone.setProperty("dragging", on)
        self.zone.style().unpolish(self.zone)
        self.zone.style().polish(self.zone)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._dragging(True)

    def dragLeaveEvent(self, event):  # noqa: N802
        self._dragging(False)

    def dropEvent(self, event):  # noqa: N802
        self._dragging(False)
        paths = [os.path.normpath(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        event.acceptProposedAction()
        self.save_paths(paths)

    def _choose(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose files to save")
        if paths:
            self.save_paths([os.path.normpath(p) for p in paths])

    # ---------------------------------------------------------------- saving
    def save_paths(self, paths):
        if not paths:
            return
        started = self.ctx.quick_save(paths, self.dest.currentData(), self, dialog=False,
                                      on_done=self._done)
        if not started:
            self._set_status("Another task is running. Try again in a moment.", "warning")

    def _done(self, results):
        level, headline, lines = summarize_quick(results)
        self._set_status(headline + "\n" + "\n".join(lines[:3]) + ("\n…" if len(lines) > 3 else ""), level)
        if level != "success":
            show_message(self, headline, "Some items could not be saved. Details:", level, "\n".join(lines))
