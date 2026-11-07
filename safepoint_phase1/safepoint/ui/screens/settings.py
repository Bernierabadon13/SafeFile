"""Settings: backup destinations (local storage + Mini Cloud), automatic backup frequency, retention."""
from __future__ import annotations

import os
import shutil

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QHBoxLayout, QLineEdit
from PySide6.QtCore import Qt

from safepoint import startup
from safepoint.config import CLOUD_MODES, RETENTION_CHOICES, SCHEDULES
from safepoint.theme import colors as C
from safepoint.ui.components import Card, list_row, make_button, make_label
from safepoint.ui.dialogs import folder_row, show_message
from safepoint.ui.screens.base import ScreenBase
from safepoint.util import human_size


class SettingsScreen(ScreenBase):
    def __init__(self, ctx):
        super().__init__(ctx, "Settings", "Where backups go, how often they run and how long they are kept")

        # ---- local storage
        self.local = QLineEdit()
        self.local.setPlaceholderText(r"e.g. D:\Backups (another drive or partition is best)")
        self.local_hint = make_label("", 12, 400, C.MUTED, wrap=True)
        local = Card("Local storage", "A folder on this PC: another partition, an external drive or a synced folder.")
        local.body.addWidget(list_row("Backup folder", None, folder_row(self.window(), self.local, "Choose the backup folder")))
        local.body.addWidget(self.local_hint)
        self.body.addWidget(local)

        # ---- mini cloud
        self.mode = QComboBox()
        for key, label in CLOUD_MODES.items():
            self.mode.addItem(label, key)
        self.embedded_root = QLineEdit()
        self.remote_url = QLineEdit()
        self.remote_url.setPlaceholderText("http://192.168.1.20:8765")
        self.remote_token = QLineEdit()
        self.remote_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.cloud_status = make_label("", 12, 400, C.MUTED, wrap=True)
        test = make_button("Test connection")
        test.clicked.connect(self._test)
        cloud = Card("Mini Cloud", "A free, self-hosted backup server. No account, no fees: you own the storage.")
        cloud.body.addWidget(list_row("Mini Cloud", None, self.mode))
        self.row_embedded = list_row("Storage folder", "Where the built-in Mini Cloud keeps its data",
                                     folder_row(self.window(), self.embedded_root, "Choose the Mini Cloud folder"))
        self.row_url = list_row("Server address", "Run SafeFile's Mini Cloud server on another device", self.remote_url)
        self.row_token = list_row("Access token", "Printed when you start the server", self.remote_token)
        for row in (self.row_embedded, self.row_url, self.row_token):
            cloud.body.addWidget(row)
        status_row = QHBoxLayout()
        status_row.addWidget(self.cloud_status, 1)
        status_row.addWidget(test)
        cloud.body.addLayout(status_row)
        cloud.body.addWidget(make_label(
            "Built-in mode stores backups on this PC only (it is not off-site). For off-site protection run the "
            "server on another computer: python -m safepoint.engine.minicloud --root FOLDER --host 0.0.0.0. "
            "Connections are not encrypted; use it on a network you trust.", 12, 400, C.MUTED, wrap=True))
        self.body.addWidget(cloud)

        # ---- automatic backup + retention
        self.schedule = QComboBox()
        self.schedule.addItems(list(SCHEDULES))
        automatic = Card("Automatic backup")
        automatic.body.addWidget(list_row("Backup frequency", "Default for new projects. Runs while SafeFile is open.", self.schedule))
        self.body.addWidget(automatic)

        self.retention = QComboBox()
        self.retention.addItems(RETENTION_CHOICES)
        retention = Card("Retention")
        retention.body.addWidget(list_row(
            "Keep versions", "Every version for 24 hours, then one per day and one per month as chosen. "
            "Cleanup happens after a verified backup.", self.retention))
        self.body.addWidget(retention)

        self.autostart = QCheckBox()
        self.show_drop = QCheckBox()
        self.close_to_tray = QCheckBox()
        startup_card = Card("Startup and tray")
        startup_card.body.addWidget(list_row(
            "Start SafeFile when Windows starts",
            "Opens in the tray so automatic backups and the quick-save window are ready." if startup.supported()
            else "Available on Windows only.", self.autostart))
        startup_card.body.addWidget(list_row("Show the quick-save window at startup",
                                             "The small drag-and-drop window opens with Windows.", self.show_drop))
        startup_card.body.addWidget(list_row("Keep running in the tray when the window is closed",
                                             "Needed for automatic backups. Quit from the tray icon.", self.close_to_tray))
        self.autostart.setEnabled(startup.supported())
        self.body.addWidget(startup_card)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch()
        discard = make_button("Discard changes")
        discard.clicked.connect(self._load_values)
        save = make_button("Save settings", "primary")
        save.clicked.connect(self._save)
        footer.addWidget(discard)
        footer.addWidget(save)
        self.body.addLayout(footer)

        self.local.textChanged.connect(self._update_hint)
        self.mode.currentIndexChanged.connect(self._update_mode)
        self._load_values()

    def refresh(self):
        self._update_hint()

    # ---------------------------------------------------------------- values
    def _load_values(self):
        s = self.repo.get_settings()
        self.local.setText(s["local_path"])
        self.mode.setCurrentIndex(max(0, self.mode.findData(s["cloud_mode"])))
        self.embedded_root.setText(s["cloud_embedded_root"])
        self.remote_url.setText(s["cloud_url"])
        self.remote_token.setText(s["cloud_token"])
        self.schedule.setCurrentText(s["default_schedule"])
        self.retention.setCurrentText(s["retention"])
        self.autostart.setChecked(startup.is_enabled())
        self.show_drop.setChecked(bool(s["show_drop_window"]))
        self.close_to_tray.setChecked(bool(s["close_to_tray"]))
        self._update_mode()
        self._update_hint()

    def _collect(self) -> dict:
        return {
            "local_path": self.local.text().strip(),
            "cloud_mode": self.mode.currentData(),
            "cloud_embedded_root": self.embedded_root.text().strip(),
            "cloud_url": self.remote_url.text().strip().rstrip("/"),
            "cloud_token": self.remote_token.text().strip(),
            "default_schedule": self.schedule.currentText(),
            "retention": self.retention.currentText(),
            "show_drop_window": self.show_drop.isChecked(),
            "close_to_tray": self.close_to_tray.isChecked(),
        }

    def _update_mode(self):
        mode = self.mode.currentData()
        self.row_embedded.setVisible(mode == "embedded")
        self.row_url.setVisible(mode == "remote")
        self.row_token.setVisible(mode == "remote")
        self.cloud_status.setText(self.ctx.cloud_status if mode != "off" else "Mini Cloud is off.")

    def _update_hint(self, *_):
        path = self.local.text().strip()
        if not path:
            self.local_hint.setText("Not set yet. Choose a folder, ideally on a different drive or partition from your files.")
            return
        probe = os.path.abspath(path)
        while not os.path.exists(probe) and probe != os.path.dirname(probe):
            probe = os.path.dirname(probe)
        text = ""
        try:
            text = f"{human_size(shutil.disk_usage(probe).free)} free on this drive. "
        except OSError:
            pass
        drive = os.path.splitdrive(os.path.abspath(path))[0].lower()
        if drive:
            same = [p.name for p in self.repo.get_projects() if os.path.splitdrive(os.path.abspath(p.path))[0].lower() == drive]
            if same:
                text += f"Same drive as {', '.join(same[:3])}: a drive failure would lose both. Use another drive for real protection."
        self.local_hint.setText(text.strip())

    # ---------------------------------------------------------------- actions
    def _save(self):
        v = self._collect()
        if v["cloud_mode"] == "embedded" and not v["cloud_embedded_root"]:
            return show_message(self.window(), "Mini Cloud folder needed", "Choose a storage folder for the built-in Mini Cloud.", "error")
        if v["cloud_mode"] == "remote" and not (v["cloud_url"].startswith("http://") or v["cloud_url"].startswith("https://")):
            return show_message(self.window(), "Check the server address", "The address must start with http:// or https://.", "error")
        self.repo.save_settings(v)
        if startup.supported():
            try:
                startup.set_enabled(self.autostart.isChecked())
            except OSError as err:
                show_message(self.window(), "Could not change startup", str(err), "error")
        self.ctx.apply_cloud_settings()
        self._update_mode()
        self.ctx.data_changed.emit()
        show_message(self.window(), "Settings saved", "Your settings are saved. " + (
            f"Mini Cloud: {self.ctx.cloud_status}." if v["cloud_mode"] != "off" else ""))

    def _test(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, message = self.ctx.test_cloud(self._collect())
        finally:
            QApplication.restoreOverrideCursor()
        show_message(self.window(), "Mini Cloud connection", message, "success" if ok else "error")
