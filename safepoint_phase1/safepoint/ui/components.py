"""Reusable UI building blocks (cards, badges, bars, tables, helpers)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from safepoint.theme import colors as C

# ---------------------------------------------------------------- basic helpers
def make_label(text="", size=13, weight=400, color=None, wrap=False, align=None) -> QLabel:
    label = QLabel(text)
    # Segoe UI Regular by default; a heavier weight only for larger headings.
    weight = 600 if (weight >= 600 and size >= 15) else 400
    label.setStyleSheet(
        f"color: {color or C.TEXT}; font-size: {size}px; font-weight: {weight}; background: transparent;"
    )
    label.setWordWrap(wrap)
    if align is not None:
        label.setAlignment(align)
    return label


def make_button(text, variant="secondary", tooltip=None, enabled=True) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setAutoDefault(False)
    button.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # focus ring appears for keyboard use, not mouse clicks
    if tooltip:
        button.setToolTip(tooltip)
    button.setEnabled(enabled)
    return button


def clear_layout(layout):
    """Remove and delete everything inside a layout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def divider() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {C.BORDER}; border: none;")
    return line


class StatusBadge(QLabel):
    def __init__(self, text: str, kind: str = "neutral"):
        super().__init__(text)
        fg, bg = C.BADGE_COLORS.get(kind, C.BADGE_COLORS["neutral"])
        self.setStyleSheet(
            f"color: {fg}; background: {bg}; border-radius: 12px; padding: 0px 10px;"
            "font-size: 12px; font-weight: 400;"
        )
        self.setFixedHeight(24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class StatusDot(QLabel):
    def __init__(self, kind: str = "neutral", size: int = 10):
        super().__init__()
        color = C.KIND_COLORS.get(kind, C.KIND_COLORS["neutral"])
        self.setFixedSize(size, size)
        self.setStyleSheet(f"background: {color}; border-radius: {size // 2}px;")


class Card(QFrame):
    """White rounded container. Add content to `card.body`."""

    def __init__(self, title=None, subtitle=None, action=None, padding=20):
        super().__init__()
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(padding, padding, padding, padding)
        outer.setSpacing(14)
        if title:
            header = QHBoxLayout()
            texts = QVBoxLayout()
            texts.setSpacing(2)
            texts.addWidget(make_label(title, 15, 600))
            if subtitle:
                texts.addWidget(make_label(subtitle, 12, 400, C.MUTED, wrap=True))
            header.addLayout(texts, 1)
            if action is not None:
                header.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)
            outer.addLayout(header)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self.body.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.body)


class SummaryCard(Card):
    def __init__(self, title, value, caption, kind="info"):
        super().__init__(padding=18)
        self.body.setSpacing(6)
        row = QHBoxLayout()
        row.addWidget(make_label(title, 12, 600, C.MUTED))
        row.addStretch()
        row.addWidget(StatusDot(kind))
        self.body.addLayout(row)
        self.body.addWidget(make_label(value, 26, 700))
        self.body.addWidget(make_label(caption, 12, 400, C.MUTED, wrap=True))


class StorageBar(QWidget):
    """Horizontal bar made of coloured segments: [(fraction 0..1, '#hex'), ...]."""

    def __init__(self, segments, height=10):
        super().__init__()
        self._segments = list(segments)
        self.setFixedHeight(height)
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(C.BORDER))
        painter.drawRoundedRect(rect, radius, radius)
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        x = rect.left()
        for fraction, color in self._segments:
            width = rect.width() * max(0.0, min(1.0, fraction))
            painter.setBrush(QColor(color))
            painter.drawRect(QRectF(x, rect.top(), width, rect.height()))
            x += width


def _paint_logo(painter: QPainter, s: float):
    """App mark: dark tile, blue outline, green check (scales with `s`)."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    outline = max(1.0, s * 0.044)
    painter.setBrush(QColor(C.ELEVATED))
    painter.setPen(QPen(QColor(C.ACCENT), outline))
    painter.drawRoundedRect(QRectF(outline / 2, outline / 2, s - outline, s - outline), s * 0.26, s * 0.26)
    pen = QPen(QColor(C.SUCCESS), max(1.6, s * 0.094))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(s * 0.28, s * 0.52)
    path.lineTo(s * 0.44, s * 0.68)
    path.lineTo(s * 0.74, s * 0.34)
    painter.drawPath(path)


LOGO_PNG = Path(__file__).resolve().parent.parent / "assets" / "safefile_logo.png"


def _logo_pixmap() -> QPixmap:
    pixmap = QPixmap(str(LOGO_PNG))  # null pixmap if the file is missing -> painted fallback is used
    return pixmap


class LogoMark(QWidget):
    """The SafeFile logo (assets/safefile_logo.png)."""

    def __init__(self, size=40):
        super().__init__()
        self.setFixedSize(size, size)
        self._pixmap = _logo_pixmap()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        if self._pixmap.isNull():
            _paint_logo(painter, self.width())
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(self.rect(), self._pixmap)


def make_app_icon() -> QIcon:
    """Window / tray icon drawn from the same logo."""
    icon = QIcon()
    source = _logo_pixmap()
    for size in (16, 24, 32, 48, 64, 128, 256):
        if source.isNull():
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            _paint_logo(painter, size)
            painter.end()
        else:
            pixmap = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        icon.addPixmap(pixmap)
    return icon


# ---------------------------------------------------------------- composite helpers
def list_row(title, subtitle=None, right=None, left=None) -> QFrame:
    row = QFrame()
    row.setObjectName("ListRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 10, 0, 10)
    layout.setSpacing(12)
    if left is not None:
        layout.addWidget(left)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    texts.addWidget(make_label(title, 13, 600))
    if subtitle:
        texts.addWidget(make_label(subtitle, 12, 400, C.MUTED))
    layout.addLayout(texts, 1)
    if right is not None:
        layout.addWidget(right, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


def key_value_grid(pairs, label_width=150) -> QWidget:
    """Two-column label/value grid on a light panel."""
    panel = QFrame()
    panel.setObjectName("KVPanel")
    panel.setStyleSheet(f"QFrame#KVPanel {{ background: {C.PANEL}; border: 1px solid {C.BORDER}; border-radius: 10px; }}")
    grid = QGridLayout(panel)
    grid.setContentsMargins(16, 14, 16, 14)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(9)
    for row, (key, value) in enumerate(pairs):
        key_label = make_label(key, 12, 600, C.MUTED)
        key_label.setFixedWidth(label_width)
        key_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
        if isinstance(value, QWidget):
            grid.addWidget(value, row, 1, Qt.AlignmentFlag.AlignLeft)
        else:
            grid.addWidget(make_label(str(value), 13, 500, wrap=True), row, 1)
    grid.setColumnStretch(1, 1)
    return panel


def notice_box(text, kind="warning") -> QFrame:
    fg, bg = C.BADGE_COLORS[kind]
    border = C.NOTICE_BORDERS.get(kind, C.BORDER)
    box = QFrame()
    box.setObjectName("NoticeBox")
    box.setStyleSheet(f"QFrame#NoticeBox {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}")
    layout = QHBoxLayout(box)
    layout.setContentsMargins(12, 9, 12, 9)
    layout.addWidget(make_label(text, 12, 500, fg, wrap=True))
    return box


# ---------------------------------------------------------------- tables
def create_table(headers, stretch_col=0) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(48)
    table.setShowGrid(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setWordWrap(False)
    table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for i in range(len(headers)):
        mode = QHeaderView.ResizeMode.Stretch if i == stretch_col else QHeaderView.ResizeMode.ResizeToContents
        header.setSectionResizeMode(i, mode)
    return table


def populate_table(table: QTableWidget, rows, muted_cols=(), bold_cols=(), fit=True):
    """Fill a table. A cell given as (text, kind) becomes a status badge."""
    table.clearContents()
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if isinstance(value, tuple):
                text, kind = value
                holder = QWidget()
                holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                layout = QHBoxLayout(holder)
                layout.setContentsMargins(10, 0, 10, 0)
                badge = StatusBadge(text, kind)
                badge_width = badge.sizeHint().width() + 4
                badge.setMinimumWidth(badge_width)       # never let the badge text be clipped
                layout.addWidget(badge)
                layout.addStretch()
                table.setCellWidget(r, c, holder)
                placeholder = QTableWidgetItem("")
                # The column auto-sizes from items, not cell widgets, so tell it how wide the badge is.
                placeholder.setSizeHint(QSize(badge_width + 20, 0))
                table.setItem(r, c, placeholder)
                continue
            item = QTableWidgetItem(str(value))
            if c in muted_cols:
                item.setForeground(QColor(C.MUTED))
            if c in bold_cols:
                item.setForeground(QColor(C.TEXT))
            table.setItem(r, c, item)
    if fit:
        body = max(len(rows), 1) * table.verticalHeader().defaultSectionSize()
        table.setFixedHeight(40 + body + 4)
