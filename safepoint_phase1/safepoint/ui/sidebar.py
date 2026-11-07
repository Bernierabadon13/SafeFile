"""Left navigation sidebar."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QVBoxLayout

from safepoint import __version__
from safepoint.theme import colors as C
from safepoint.ui.components import LogoMark, make_button, make_label


class Sidebar(QFrame):
    navigate = Signal(str)

    def __init__(self, items):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(236)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 22, 16, 18)
        layout.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(LogoMark())
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(make_label("SafeFile", 21, 400))
        names.addWidget(make_label("Backup & recovery", 11, 400, C.MUTED))
        brand.addLayout(names, 1)
        layout.addLayout(brand)
        layout.addSpacing(22)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for index, (key, label) in enumerate(items, 1):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"Ctrl+{index}")
            button.clicked.connect(lambda _checked=False, k=key: self.navigate.emit(k))
            self._group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        footer = QVBoxLayout()
        footer.setSpacing(8)
        quick = make_button("Quick save window")
        quick.setToolTip("Open the small drag-and-drop window")
        quick.clicked.connect(lambda: self.navigate.emit("dropwindow"))
        footer.addWidget(quick)
        self.status = make_label("Idle", 12, 400, C.MUTED, wrap=True)
        footer.addWidget(self.status)
        footer.addWidget(make_label(f"v{__version__}", 11, 400, C.FAINT))
        layout.addLayout(footer)

    def set_status(self, text: str):
        self.status.setText(text)

    def set_active(self, key: str):
        self._buttons[key].setChecked(True)
