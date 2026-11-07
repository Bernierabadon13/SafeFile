"""Typeface policy: Segoe UI only. Never substituted silently.

Segoe UI ships with Windows 10 and 11 and is not redistributable, so it is
NOT bundled with this project. `check_font()` reports whether Qt can actually
resolve it, and the app warns the user if it cannot.
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

FONT_FAMILY = "Segoe UI"


def check_font() -> tuple[bool, str]:
    """Return (available, human-readable message)."""
    families = QFontDatabase.families()
    if FONT_FAMILY not in families:
        return False, (
            f"The font '{FONT_FAMILY}' was not found on this system. "
            "SafeFile is designed for Segoe UI, which is included with Windows 10 and 11. "
            "The interface will display with a different font until Segoe UI is available."
        )
    resolved = QFontInfo(QFont(FONT_FAMILY)).family()
    if resolved != FONT_FAMILY:
        return False, (
            f"Qt resolved '{FONT_FAMILY}' to '{resolved}' instead. "
            "The interface is not using Segoe UI."
        )
    styles = ", ".join(QFontDatabase.styles(FONT_FAMILY))
    return True, f"Font check passed: {FONT_FAMILY} is available (styles: {styles})."


def application_font() -> QFont:
    font = QFont(FONT_FAMILY)
    font.setPointSize(10)
    font.setWeight(QFont.Weight.Normal)
    return font
