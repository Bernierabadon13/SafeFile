"""Global Qt stylesheet (QSS). Press F5 in the running app to reload it."""
from string import Template

from . import colors as C
from .fonts import FONT_FAMILY

_QSS = Template(
    """
QWidget {
    font-family: "$FONT";
    font-size: 13px;
    color: $TEXT;
}
QMainWindow { background: $BG; }
QWidget#Root, QWidget#Content { background: $BG; }
QScrollArea { background: $BG; border: none; }
QDialog { background: $CARD; }
QLabel { background: transparent; }
QToolTip { background: $ELEVATED; color: $TEXT; border: 1px solid $BORDER; padding: 6px 8px; }

QFrame#Card {
    background: $CARD;
    border: 1px solid $BORDER;
    border-radius: 10px;
}
QFrame#ListRow { background: transparent; border: none; border-bottom: 1px solid $ROW_DIVIDER; }

/* ---------- Sidebar ---------- */
QFrame#Sidebar { background: $SIDEBAR; border: none; border-right: 1px solid $BORDER; }
QPushButton#NavButton {
    min-width: 0px;
    text-align: left;
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 6px;
    padding: 10px 14px;
    color: $MUTED;
    font-weight: 400;
}
QPushButton#NavButton:hover { background: $CARD; color: $TEXT; }
QPushButton#NavButton:checked { background: $ACCENT_TINT; color: $TEXT; border-left: 3px solid $ACCENT; }

/* ---------- Section tabs (Backups) ---------- */
QPushButton#TabButton {
    min-width: 0px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 8px 14px;
    color: $MUTED;
    font-weight: 400;
}
QPushButton#TabButton:hover { color: $TEXT; background: transparent; }
QPushButton#TabButton:checked { color: $TEXT; border-bottom: 2px solid $ACCENT; background: transparent; }

/* ---------- Buttons ---------- */
/* Secondary (default): lighter surface + visible border */
QPushButton {
    background: $BUTTON_BG;
    border: 1px solid $BUTTON_BORDER;
    border-radius: 6px;
    padding: 8px 16px;
    min-width: 64px;
    min-height: 18px;
    color: $TEXT;
    font-weight: 400;
}
QPushButton:hover { background: $BUTTON_HOVER_BG; border-color: $ACCENT; }
QPushButton:pressed { background: $BUTTON_PRESSED_BG; border-color: $ACCENT; }
QPushButton:focus { border-color: $FOCUS_RING; }
QPushButton:disabled { background: $BUTTON_DISABLED_BG; border-color: $BUTTON_DISABLED_BORDER; color: $FAINT; }

/* Primary: blue fill */
QPushButton[variant="primary"] { background: $ACCENT; border: 1px solid $ACCENT_EDGE; color: $TEXT_ON_ACCENT; }
QPushButton[variant="primary"]:hover { background: $ACCENT_HOVER; border-color: $ACCENT_EDGE; }
QPushButton[variant="primary"]:pressed { background: $ACCENT_PRESSED; border-color: $ACCENT_EDGE; }
QPushButton[variant="primary"]:focus { border: 1px solid $FOCUS_RING; }
QPushButton[variant="primary"]:disabled { background: $ACCENT_DISABLED; border: 1px solid $ACCENT_DISABLED_BORDER; color: $MUTED; }

/* Destructive: red text and border on a dark red surface */
QPushButton[variant="danger"] { background: $ERROR_TINT; border: 1px solid $DANGER_BORDER; color: $ERROR; }
QPushButton[variant="danger"]:hover { background: $DANGER_HOVER_BG; border-color: $ERROR; }
QPushButton[variant="danger"]:pressed { background: $DANGER_PRESSED_BG; border-color: $ERROR; }
QPushButton[variant="danger"]:focus { border: 1px solid $FOCUS_RING; }
QPushButton[variant="danger"]:disabled { background: $BUTTON_DISABLED_BG; border: 1px solid $BUTTON_DISABLED_BORDER; color: $FAINT; }

/* Tertiary / link-style: outlined blue, always visible */
QPushButton[variant="link"] { background: $ACCENT_TINT; border: 1px solid $LINK_BORDER; color: $ACCENT_TEXT; padding: 6px 12px; }
QPushButton[variant="link"]:hover { background: $LINK_HOVER_BG; border-color: $ACCENT_TEXT; }
QPushButton[variant="link"]:pressed { background: $LINK_PRESSED_BG; border-color: $ACCENT_TEXT; }
QPushButton[variant="link"]:focus { border: 1px solid $FOCUS_RING; }
QPushButton[variant="link"]:disabled { background: $BUTTON_DISABLED_BG; border: 1px solid $BUTTON_DISABLED_BORDER; color: $FAINT; }

/* ---------- Inputs ---------- */
QLineEdit, QComboBox {
    background: $BG;
    border: 1px solid $BORDER;
    border-radius: 6px;
    padding: 7px 10px;
    color: $TEXT;
    placeholder-text-color: $FAINT;
    selection-background-color: $ACCENT;
    selection-color: $TEXT_ON_ACCENT;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid $ACCENT; }
QLineEdit:disabled, QComboBox:disabled { background: $CARD; color: $FAINT; }
QComboBox { padding-right: 28px; min-height: 18px; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    image: none;
    width: 0px; height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid $MUTED;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background: $ELEVATED;
    color: $TEXT;
    border: 1px solid $BORDER;
    selection-background-color: $ACCENT_TINT;
    selection-color: $TEXT;
    outline: none;
}
QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
QCheckBox::indicator, QTreeWidget::indicator {
    width: 16px; height: 16px;
    border: 1px solid $FIELD_BORDER; border-radius: 4px; background: $BG;
}
QCheckBox::indicator:checked, QTreeWidget::indicator:checked {
    background: $ACCENT; border-color: $ACCENT;
}
QCheckBox::indicator:indeterminate, QTreeWidget::indicator:indeterminate {
    background: $ACCENT_TINT; border-color: $ACCENT;
}
QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid $FIELD_BORDER; border-radius: 8px; background: $BG;
}
QRadioButton::indicator:checked {
    width: 8px; height: 8px; border: 4px solid $ACCENT; border-radius: 8px; background: $BG;
}

/* ---------- Tables, trees, lists ---------- */
QTableWidget, QTreeWidget {
    background: $CARD;
    border: none;
    gridline-color: transparent;
    selection-background-color: $ACCENT_TINT;
    selection-color: $TEXT;
    outline: none;
}
QTableCornerButton::section { background: $CARD; border: none; }
QTableWidget::item { padding: 4px 10px; border-bottom: 1px solid $ROW_DIVIDER; }
QTableWidget::item:hover, QTreeWidget::item:hover { background: $HOVER_SUBTLE; }
QTableWidget::item:selected, QTreeWidget::item:selected { background: $ACCENT_TINT; color: $TEXT; }
QTreeWidget::item { padding: 5px 4px; }
QHeaderView { background: $CARD; border: none; }
QHeaderView::section {
    background: $CARD;
    color: $MUTED;
    border: none;
    border-bottom: 1px solid $BORDER;
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 400;
}
QListWidget {
    background: $BG;
    border: 1px solid $BORDER;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QListWidget::item { padding: 9px 10px; border-radius: 4px; }
QListWidget::item:hover { background: $HOVER_SUBTLE; }
QListWidget::item:selected { background: $ACCENT_TINT; color: $TEXT; }

/* ---------- Drop window and menus ---------- */
QWidget#DropWindow { background: $BG; }
QFrame#DropZone { background: $CARD; border: 2px dashed $FIELD_BORDER; border-radius: 12px; }
QFrame#DropZone[dragging="true"] { background: $ACCENT_TINT; border: 2px dashed $ACCENT; }
QMenu { background: $ELEVATED; border: 1px solid $BORDER; padding: 4px; }
QMenu::item { padding: 7px 24px 7px 14px; border-radius: 4px; }
QMenu::item:selected { background: $ACCENT_TINT; }
QMenu::separator { height: 1px; background: $BORDER; margin: 4px 6px; }

/* ---------- Progress ---------- */
QProgressBar { background: $BORDER; border: none; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: $ACCENT; border-radius: 4px; }
QPlainTextEdit {
    background: $BG; border: 1px solid $BORDER; border-radius: 6px; padding: 6px 8px; color: $TEXT;
    selection-background-color: $ACCENT; selection-color: $TEXT_ON_ACCENT;
}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $SCROLL_HANDLE; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $SCROLL_HOVER; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $SCROLL_HANDLE; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: $SCROLL_HOVER; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""
)


def build_stylesheet() -> str:
    return _QSS.substitute(
        FONT=FONT_FAMILY,
        BG=C.BACKGROUND, SIDEBAR=C.SIDEBAR, CARD=C.CARD, ELEVATED=C.ELEVATED,
        TEXT=C.TEXT, MUTED=C.MUTED, FAINT=C.FAINT, BORDER=C.BORDER,
        ACCENT=C.ACCENT, ACCENT_TINT=C.ACCENT_TINT, ACCENT_TEXT=C.ACCENT_TEXT,
        ACCENT_HOVER=C.ACCENT_HOVER, ACCENT_PRESSED=C.ACCENT_PRESSED,
        ACCENT_DISABLED=C.ACCENT_DISABLED, TEXT_ON_ACCENT=C.TEXT_ON_ACCENT,
        HOVER_SUBTLE=C.HOVER_SUBTLE, ROW_DIVIDER=C.ROW_DIVIDER, FIELD_BORDER=C.FIELD_BORDER,
        SCROLL_HANDLE=C.SCROLL_HANDLE, SCROLL_HOVER=C.SCROLL_HOVER,
        ERROR=C.ERROR, ERROR_TINT=C.ERROR_TINT, ERROR_BORDER=C.ERROR_BORDER,
        WARNING_BORDER=C.WARNING_BORDER, BANNER=C.BANNER,
        ACCENT_EDGE=C.ACCENT_EDGE, ACCENT_DISABLED_BORDER=C.ACCENT_DISABLED_BORDER,
        BUTTON_BG=C.BUTTON_BG, BUTTON_BORDER=C.BUTTON_BORDER, BUTTON_HOVER_BG=C.BUTTON_HOVER_BG,
        BUTTON_PRESSED_BG=C.BUTTON_PRESSED_BG, BUTTON_DISABLED_BG=C.BUTTON_DISABLED_BG,
        BUTTON_DISABLED_BORDER=C.BUTTON_DISABLED_BORDER, FOCUS_RING=C.FOCUS_RING,
        DANGER_BORDER=C.DANGER_BORDER, DANGER_HOVER_BG=C.DANGER_HOVER_BG,
        DANGER_PRESSED_BG=C.DANGER_PRESSED_BG, LINK_BORDER=C.LINK_BORDER,
        LINK_HOVER_BG=C.LINK_HOVER_BG, LINK_PRESSED_BG=C.LINK_PRESSED_BG,
    )
