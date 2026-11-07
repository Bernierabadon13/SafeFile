"""Application bootstrap."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from safepoint import APP_NAME
from safepoint.config import db_path
from safepoint.db.database import Database
from safepoint.db.sqlite_repository import SqliteRepository
from safepoint.engine.engine import BackupEngine
from safepoint.logging_setup import setup_logging
from safepoint.ui.context import AppContext
from safepoint.theme.palette import build_palette
from safepoint.theme.fonts import FONT_FAMILY, application_font, check_font
from safepoint.theme.styles import build_stylesheet
from safepoint.ui.components import make_app_icon
from safepoint.ui.main_window import VIEWS, MainWindow


SINGLE_INSTANCE_NAME = "SafeFile.SingleInstance"


def _signal_running_instance(show: bool) -> bool:
    """If SafeFile is already running, tell it to show its window and return True."""
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_NAME)
    if not socket.waitForConnected(500):
        return False
    if show:
        socket.write(b"show")
        socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SafeFile backup and recovery")
    parser.add_argument("--screen", choices=VIEWS + ["backups"], default="home",
                        help="screen to open first")
    parser.add_argument("--minimized", action="store_true",
                        help="start in the tray (used when Windows starts)")
    parser.add_argument("--screenshots", metavar="DIR",
                        help="save a PNG of every screen into DIR, then exit")
    args = parser.parse_args(argv)

    if os.name == "nt":  # lets the taskbar show SafeFile's own icon instead of Python's
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SafeFile.Desktop")
        except Exception:
            pass
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # the tray keeps SafeFile alive when windows are closed
    log = setup_logging()
    if not args.screenshots and _signal_running_instance(show=not args.minimized):
        return 0  # already running: the existing window was brought forward
    app.setStyle("Fusion")
    font_ok, font_message = check_font()
    log.info(font_message)
    app.setFont(application_font())
    app.setPalette(build_palette())
    app.setStyleSheet(build_stylesheet())

    db = Database(db_path())
    ctx = AppContext(SqliteRepository(db), BackupEngine(db))
    app.aboutToQuit.connect(ctx.shutdown)
    window = MainWindow(ctx)
    app.setWindowIcon(make_app_icon())

    server = QLocalServer(app)
    QLocalServer.removeServer(SINGLE_INSTANCE_NAME)
    server.listen(SINGLE_INSTANCE_NAME)

    def on_second_launch():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.waitForReadyRead(200)
            wants_window = bytes(conn.readAll()) == b"show"
            conn.close()
            conn.deleteLater()
            if wants_window:
                window.tray.show_main()

    server.newConnection.connect(on_second_launch)
    window.navigate(args.screen)
    if args.minimized and window.tray.available and not args.screenshots:
        if ctx.repo.get_settings().get("show_drop_window", True):
            window.tray.show_drop()
    else:
        window.show()

    if not font_ok and not args.screenshots:
        QMessageBox.warning(window, f"{FONT_FAMILY} not found", font_message)

    if args.screenshots:
        out = Path(args.screenshots)
        out.mkdir(parents=True, exist_ok=True)
        for key in VIEWS:
            window.navigate(key)
            app.processEvents()
            window.grab().save(str(out / f"{key}.png"))
        print(f"Saved {len(VIEWS)} screenshots to {out.resolve()}")
        return 0

    return app.exec()
