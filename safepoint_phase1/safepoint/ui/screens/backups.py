"""Backups: saved projects, version history and file restoration in one section."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from safepoint.ui.screens.history import HistoryScreen
from safepoint.ui.screens.projects import ProjectsScreen
from safepoint.ui.screens.quicksaves import QuickSavesScreen
from safepoint.ui.screens.recovery import RecoveryScreen


class BackupsScreen(QWidget):
    navigate = Signal(str)

    TABS = [("projects", "Projects", ProjectsScreen),
            ("history", "Version history", HistoryScreen),
            ("recovery", "Restore", RecoveryScreen),
            ("quick", "Quick saves", QuickSavesScreen)]

    def __init__(self, ctx):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(32, 16, 32, 0)
        row.setSpacing(4)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._stack = QStackedWidget()
        self._buttons, self._index, self._screens = {}, {}, {}
        for key, label, cls in self.TABS:
            button = QPushButton(label)
            button.setObjectName("TabButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, k=key: self.show_tab(k))
            self._group.addButton(button)
            row.addWidget(button)
            self._buttons[key] = button
            screen = cls(ctx)
            screen.navigate.connect(self.navigate)
            self._index[key] = self._stack.addWidget(screen)
            self._screens[key] = screen
        row.addStretch()
        outer.addWidget(bar)
        outer.addWidget(self._stack, 1)
        self._current = "projects"
        self.show_tab("projects")

    def show_tab(self, key: str):
        if key not in self._index:
            return
        self._current = key
        self._buttons[key].setChecked(True)
        self._stack.setCurrentIndex(self._index[key])
        self._screens[key].on_show()

    def on_show(self):
        self._screens[self._current].on_show()
