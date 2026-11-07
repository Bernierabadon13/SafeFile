"""Shared base class for all screens."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from safepoint.theme import colors as C
from safepoint.ui.components import make_label


class ScreenBase(QWidget):
    """Scrollable page with a title row. Add content to `self.body`. Override `refresh()`."""

    navigate = Signal(str)

    def __init__(self, ctx, title: str, subtitle: str = ""):
        super().__init__()
        self.ctx = ctx
        self.repo = ctx.repo
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setStyleSheet(f"background: {C.BACKGROUND};")
        outer.addWidget(scroll)
        content = QWidget()
        content.setObjectName("Content")
        scroll.setWidget(content)
        self.page = QVBoxLayout(content)
        self.page.setContentsMargins(32, 28, 32, 32)
        self.page.setSpacing(20)

        header = QHBoxLayout()
        texts = QVBoxLayout()
        texts.setSpacing(3)
        texts.addWidget(make_label(title, 24, 600))
        if subtitle:
            texts.addWidget(make_label(subtitle, 13, 400, C.MUTED))
        header.addLayout(texts, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        header.addLayout(self.actions)
        self.page.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setSpacing(20)
        self.page.addLayout(self.body)
        self.page.addStretch(1)
        ctx.data_changed.connect(self.refresh)

    def add_action(self, button):
        self.actions.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)

    def go(self, key: str):
        self.navigate.emit(key)

    def refresh(self):
        """Reload data from the repository. Called when data changes and when the screen is shown."""

    def on_show(self):
        self.refresh()
