"""System tray icon and the drop window."""
from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from safepoint.ui.components import make_app_icon
from safepoint.ui.dropwindow import DropWindow


class TrayController(QObject):
    def __init__(self, ctx, main_window):
        super().__init__(main_window)
        self.main = main_window
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self.drop = DropWindow(ctx, self._open_section)
        self.tray = None
        if not self.available:
            return
        self.tray = QSystemTrayIcon(make_app_icon(), self)
        self.tray.setToolTip("SafeFile")
        menu = QMenu()
        for text, handler in (("Open SafeFile", lambda: self.show_main()),
                              ("Quick save window", lambda: self.show_drop())):
            action = QAction(text, menu)
            action.triggered.connect(handler)
            menu.addAction(action)
        menu.addSeparator()
        quit_action = QAction("Quit SafeFile", menu)
        quit_action.triggered.connect(main_window.quit_app)
        menu.addAction(quit_action)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_drop()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main()

    def _open_section(self, key):
        self.show_main()
        self.main.navigate(key)

    def show_main(self):
        self.main.showNormal()
        self.main.raise_()
        self.main.activateWindow()

    def show_drop(self):
        self.drop.show()
        self.drop.raise_()
        self.drop.activateWindow()

    def notify(self, title, text):
        if self.tray:
            self.tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 6000)

    def close(self):
        self.drop.close()
        if self.tray:
            self.tray.hide()
