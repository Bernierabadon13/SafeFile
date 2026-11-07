# SafeFile

Windows backup and file recovery. Back up folders to **local storage** (another partition, an external
drive or a synced folder) and/or to a free, self-hosted **Mini Cloud**. Every backup is read back and
checked before SafeFile says it succeeded.

## Requirements
- Windows 10 or 11 (Segoe UI is included with Windows)
- Python 3.10 or newer, installed with "Add python.exe to PATH"

## Install and launch (PowerShell, one line at a time)
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd C:\Users\imusa\Desktop\safepoint\safepoint_phase1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```
Next launches: `.\.venv\Scripts\python.exe main.py`

## First run
1. **Settings** → choose a **Local storage** folder (ideally on another drive or partition) → Save settings.
2. **Home** → Add Project… → pick the folder to protect, where to back up (Local, Mini Cloud or both) and how often.
3. **Back Up Now**. A progress window shows real progress; the result says "verified" only after the backup was read back.
4. To recover: **Restore files** (Home) or **Backups → Restore**: pick a version, tick files, choose a folder, restore.

## Quick saves (drag and drop)
A small always-on-top window for saving a file or folder **whenever you want**.
- **Drop** files or folders on the window (or press *Choose files…*): each one is saved as a new version and verified.
- **Own history:** every file or folder has its own list of versions (**Backups → Quick saves**). Saving again always makes a new version, even if the content is the same; storage is not wasted because identical content is stored once.
- **Save new version** (with an optional note) and **Restore** any version to a new folder, or back over the original after a confirmation.
- Quick-save versions are **never removed by retention**; they stay until you remove the item.
- Nothing is watched: a version is made only when you drop, add or press the button.

## Start with Windows and the tray
Settings → **Startup and tray**: start SafeFile with Windows (opens in the tray, with the quick-save window), and keep it running in the tray when the window is closed so automatic backups continue. Quit from the tray icon. Click the tray icon for the quick-save window, double-click for the main window.

## What it does
- **Versions:** every changed backup is saved as a version (history). Unchanged folders create no new version.
- **Deduplication:** identical file content is stored once per destination.
- **Verification:** SHA-256 fingerprints; damaged or missing data marks the version "Failed". Restores also check each file.
- **Both destinations:** with "Local storage + Mini Cloud", restore falls back to the other copy if one is damaged.
- **Automatic backups:** run on the chosen schedule **while SafeFile is running** (it can stay in the tray; checked every minute).
- **Retention:** every version for 24 hours, then one per day / month per your setting; cleanup happens only after a verified backup.
- **Cancel** any backup, verify or restore. A cancelled backup is never recorded as a version.

## Mini Cloud (free, no account)
A small server included in SafeFile (`safepoint/engine/minicloud.py`, standard library only).
- **Built into SafeFile:** runs inside the app on this PC only (127.0.0.1). Handy, but not off-site.
- **Another device:** for real off-site protection run it on a second computer, an old laptop or a Raspberry Pi:
  ```
  python -m safepoint.engine.minicloud --root D:\MiniCloud --host 0.0.0.0 --port 8765
  ```
  It prints an access token. In SafeFile: Settings → Mini Cloud → Another device → enter `http://<that-pc>:8765` and the token.
  Allow the port in the firewall of that computer.
- **Security:** traffic is plain HTTP with a token. Use it on localhost or a network you trust. Backups are **not encrypted**.

## Where data lives
- SafeFile's database: `%LOCALAPPDATA%\SafeFile\safefile.db` (override with the `SAFEFILE_HOME` environment variable).
- Backups: `<your local folder>\SafeFile\` and/or the Mini Cloud folder. Each version also stores a readable manifest next to the data.

## Known limits
- Files locked by other programs, or changing while being read, are skipped and reported on the version.
- Windows paths longer than 260 characters may be skipped.
- Automatic backups need the app open. Encryption and cloud providers such as Google Drive are not included
  (a synced folder such as Google Drive or OneDrive can be chosen as the Local storage folder).

## Tests
```powershell
python -m unittest discover -s tests -v
```
Covers backup, verification, restore, corruption detection, Mini Cloud, dual destinations, retention and cleanup.

## Build an installer (SafeFile-Setup.exe)
Needs Windows, the `.venv` from the install steps and [Inno Setup 6](https://jrsoftware.org/isinfo.php) (free).
```powershell
cd C:\Users\imusa\Desktop\safepoint\safepoint_phase1
.\build.bat
```
- Result: `installer_output\SafeFile-Setup-<version>.exe`. Without Inno Setup the build still makes `dist\SafeFile\SafeFile.exe` for testing.
- It installs for the current user (no administrator needed), adds Start menu and optional desktop shortcuts, an optional
  "Start with Windows" and an uninstaller. Backups and settings in `%LOCALAPPDATA%\SafeFile` are **kept** when you uninstall.
- `SafeFileMiniCloud.exe` is installed too: the stand-alone Mini Cloud server for another PC (`SafeFileMiniCloud.exe --root D:\MiniCloud --host 0.0.0.0`).
- Test first: run `dist\SafeFile\SafeFile.exe`, then install the setup file on a PC (or Windows Sandbox) that has no Python.
- Unsigned installers trigger Windows SmartScreen: tell classmates to click **More info → Run anyway**.
- Opening SafeFile twice just brings the running copy forward. Problems are written to `%LOCALAPPDATA%\SafeFile\safefile.log`.
- To release a new version: raise `__version__` in `safepoint/__init__.py` and run `build.bat` again.

## App icon
The logo is `safepoint/assets/safefile_logo.png` (window, tray and sidebar). `safepoint/assets/safefile.ico` is the same
logo for Windows shortcuts and the future installer: right-click a shortcut → Properties → Change Icon → Browse to it.

## Revising the interface
| To change | Edit |
|---|---|
| Colors / global look | `safepoint/theme/colors.py`, `styles.py` (press F5 in the app to reload) |
| Screens | `safepoint/ui/screens/` |
| Dialogs | `safepoint/ui/dialogs.py` |
| Engine | `safepoint/engine/` |
| Database | `safepoint/db/` |

Ctrl+1 / Ctrl+2 / Ctrl+3 switch sections. `python main.py --screenshots shots` saves a PNG of each view.
