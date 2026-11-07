"""Plain data containers shared by the UI and (later) the real data layer."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    category: str
    path: str
    destination: str
    schedule: str
    last_snapshot: str
    size: str
    file_count: int
    status_label: str
    status_kind: str  # success | warning | error | info | neutral
    note: str = ""
    exclusions: tuple = ()
    destination_key: str = "local"
    paused: bool = False
    last_ok: str = "Never"


@dataclass(frozen=True)
class Snapshot:
    id: str
    project: str
    created: str
    kind: str  # Scheduled | Manual
    files: int
    size: str
    verification: str
    verification_kind: str
    added: int
    modified: int
    removed: int
    note: str = ""
    project_id: str = ""
    detail: str = ""


@dataclass(frozen=True)
class QuickItem:
    """A file or folder saved on demand (drag and drop), with its own version history."""
    id: str
    name: str
    path: str
    is_folder: bool
    exists: bool
    versions: int
    last_saved: str
    status_label: str
    status_kind: str
    destination: str
    destination_key: str


@dataclass(frozen=True)
class ChangedFile:
    change: str  # Added | Modified | Removed
    path: str
    size: str


@dataclass(frozen=True)
class ActivityEntry:
    time: str
    level: str  # info | success | warning | error
    category: str
    message: str
    detail: str = ""


@dataclass(frozen=True)
class StorageLocation:
    name: str
    kind: str
    path: str
    used_gb: float
    total_gb: float
    status: str
    status_kind: str
    note: str = ""
    configured: bool = True


@dataclass(frozen=True)
class MissingFile:
    name: str
    original_path: str
    last_seen: str
    size: str
    snapshot_id: str
    rel_path: str = ""
    project_id: str = ""
    project_name: str = ""


@dataclass(frozen=True)
class TreeNode:
    name: str
    is_folder: bool = False
    size: str = ""
    modified: str = ""
    children: tuple = ()
    path: str = ""   # relative path of a file (empty for folders)


@dataclass(frozen=True)
class OverviewStats:
    protected: int
    total: int
    attention: int
    latest_snapshot_time: str
    latest_snapshot_caption: str
    storage_used_gb: float
    connected_locations: int
