"""Dark QPalette so any widget not covered by the stylesheet still matches the theme."""
from PySide6.QtGui import QColor, QPalette

from . import colors as C


def build_palette() -> QPalette:
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: C.BACKGROUND,
        QPalette.ColorRole.WindowText: C.TEXT,
        QPalette.ColorRole.Base: C.CARD,
        QPalette.ColorRole.AlternateBase: C.ELEVATED,
        QPalette.ColorRole.Text: C.TEXT,
        QPalette.ColorRole.Button: C.ELEVATED,
        QPalette.ColorRole.ButtonText: C.TEXT,
        QPalette.ColorRole.ToolTipBase: C.ELEVATED,
        QPalette.ColorRole.ToolTipText: C.TEXT,
        QPalette.ColorRole.Highlight: C.ACCENT_TINT,
        QPalette.ColorRole.HighlightedText: C.TEXT,
        QPalette.ColorRole.PlaceholderText: C.FAINT,
        QPalette.ColorRole.Link: C.ACCENT_TEXT,
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(C.FAINT))
    return p
