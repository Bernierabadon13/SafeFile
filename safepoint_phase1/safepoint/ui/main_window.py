"""Main window: sidebar + three sections (Home, Backups, Settings)."""
from __future__ import annotations

import importlib

from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from safepoint.theme import colors, palette, styles
from safepoint.ui.components import make_app_icon
from safepoint.ui.dialogs import confirm
from safepoint.ui.screens.backups import BackupsScreen
from safepoint.ui.screens.home import HomeScreen
from safepoint.ui.screens.settings import SettingsScreen
from safepoint.ui.sidebar import Sidebar
from safepoint.ui.tray import TrayController

NAV_ITEMS = [
    ("home", "Home"),
    ("backups", "Backups"),
    ("settings", "Settings"),
]

SCREEN_CLASSES = {
    "home": HomeScreen,
    "backups": BackupsScreen,
    "settings": SettingsScreen,
}

# Deep links: a view name -> (section, tab)
ALIASES = {
    "projects": ("backups", "projects"),
    "history": ("backups", "history"),
    "recovery": ("backups", "recovery"),
    "quick": ("backups", "quick"),
}

# Every distinct view, used by --screen and --screenshots
VIEWS = ["home", "projects", "history", "recovery", "settings"]


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._quitting = False
        self._tray_hint_shown = False
        self.setWindowIcon(make_app_icon())
        self.setWindowTitle("SafeFile")
        self.resize(1280, 840)
        self.setMinimumSize(1000, 660)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = Sidebar(NAV_ITEMS)
        row.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setSpacing(0)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        row.addLayout(right, 1)

        self._index = {}
        self._screens = {}
        for key, _label in NAV_ITEMS:
            screen = SCREEN_CLASSES[key](ctx)
            screen.navigate.connect(self.navigate)
            self._index[key] = self.stack.addWidget(screen)
            self._screens[key] = screen

        self.sidebar.navigate.connect(self.navigate)
        for i, (key, _label) in enumerate(NAV_ITEMS, 1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, activated=lambda k=key: self.navigate(k))
        QShortcut(QKeySequence("F5"), self, activated=self.reload_theme)
        ctx.activity.connect(self.sidebar.set_status)

        # automatic backups: check once shortly after start, then every minute while the app is open
        self._timer = QTimer(self)
        self._timer.timeout.connect(ctx.check_schedule)
        self._timer.start(60_000)
        QTimer.singleShot(5_000, ctx.check_schedule)
        self.tray = TrayController(ctx, self)
        self.navigate("home")

    def quit_app(self):
        self.close_for_real()

    def close_for_real(self):
        if self.ctx.busy() and not confirm(
                self, "A task is still running",
                "SafeFile is still working. Quitting now cancels it; no unfinished backup is marked as verified.",
                "Quit anyway", danger=True):
            return
        self._quitting = True
        self.tray.close()
        self.ctx.shutdown()
        QApplication.instance().quit()

    def closeEvent(self, event):  # noqa: N802
        if (not self._quitting and self.tray.available
                and self.ctx.repo.get_settings().get("close_to_tray", True)):
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.notify("SafeFile is still running",
                                 "Automatic backups continue. Use the tray icon to open SafeFile or quit.")
            return
        if not self._quitting:
            event.ignore()
            self.close_for_real()
            return
        event.accept()

    def navigate(self, key: str):
        if key == "dropwindow":
            self.tray.show_drop()
            return
        tab = None
        if key in ALIASES:
            key, tab = ALIASES[key]
        if key not in self._index:
            return
        screen = self._screens[key]
        self.stack.setCurrentIndex(self._index[key])
        self.sidebar.set_active(key)
        if tab is not None and hasattr(screen, "show_tab"):
            screen.show_tab(tab)
        else:
            screen.on_show()

    def reload_theme(self):
        """Dev helper: re-read colors.py and styles.py and re-apply the stylesheet and palette."""
        importlib.reload(colors)
        importlib.reload(styles)
        app = QApplication.instance()
        app.setPalette(palette.build_palette())
        app.setStyleSheet(styles.build_stylesheet())
