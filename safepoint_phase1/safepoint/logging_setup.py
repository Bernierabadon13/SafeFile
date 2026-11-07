"""Log file for diagnosing problems: %LOCALAPPDATA%\\SafeFile\\safefile.log (rotates at 1 MB)."""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from safepoint import __version__
from safepoint.config import app_home


def log_path():
    return app_home() / "safefile.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("safefile")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        handler = RotatingFileHandler(log_path(), maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    except OSError:
        return logger
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

    def on_uncaught(exc_type, exc, tb):
        logger.critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        if sys.__stderr__ is not None:
            sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = on_uncaught
    threading.excepthook = lambda a: logger.critical("Uncaught thread exception",
                                                     exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    logger.info("SafeFile %s starting", __version__)
    return logger
