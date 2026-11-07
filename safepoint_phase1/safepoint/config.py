"""Application paths, defaults and the fixed choices offered in the UI."""
from __future__ import annotations

import os
from pathlib import Path


def app_home() -> Path:
    """Folder for SafeFile's own data (database). Override with SAFEFILE_HOME."""
    env = os.environ.get("SAFEFILE_HOME")
    if env:
        base = Path(env)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "SafeFile"
    else:
        base = Path.home() / ".safefile"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return app_home() / "safefile.db"


# schedule label -> seconds between automatic backups (None = manual only)
SCHEDULES = {
    "Every 30 minutes": 1800,
    "Every hour": 3600,
    "Daily": 86400,
    "Weekly": 604800,
    "Manual only": None,
}

DESTINATIONS = {
    "local": "Local storage",
    "cloud": "Mini Cloud",
    "both": "Local storage + Mini Cloud",
}

RETENTION_CHOICES = ["7 daily", "30 daily, 12 monthly", "90 daily, 24 monthly", "Keep everything"]

CLOUD_MODES = {
    "off": "Off",
    "embedded": "Built into SafeFile (this PC)",
    "remote": "Another device",
}

DEFAULT_EXCLUSIONS = ["node_modules", "__pycache__", ".venv", "*.tmp", "~$*", "Thumbs.db"]
EMBEDDED_PORT = 8765


def default_settings() -> dict:
    return {
        "local_path": "",  # the user chooses this themselves
        "cloud_mode": "embedded",
        "cloud_embedded_root": str(app_home() / "MiniCloud"),
        "cloud_embedded_port": EMBEDDED_PORT,
        "cloud_embedded_token": "",
        "cloud_url": "",
        "cloud_token": "",
        "default_schedule": "Every hour",
        "retention": "30 daily, 12 monthly",
        "default_exclusions": list(DEFAULT_EXCLUSIONS),
        "selected_project": "",
        "quick_destination": "local",
        "show_drop_window": True,
        "close_to_tray": True,
    }
