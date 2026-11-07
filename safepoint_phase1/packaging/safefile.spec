# -*- mode: python ; coding: utf-8 -*-
# PyInstaller recipe for the SafeFile desktop app (folder build: dist/SafeFile/SafeFile.exe).
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "safepoint" / "assets"), "safepoint/assets")],   # logo and icon
    hiddenimports=[],
    excludes=["tkinter", "test", "pydoc_data"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SafeFile",
    icon=str(ROOT / "safepoint" / "assets" / "safefile.ico"),
    console=False,          # no black window
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SafeFile")
