@echo off
setlocal
cd /d "%~dp0"
echo === SafeFile installer build ===

if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment .venv was not found. Create it first, as in the Install and launch section of README.md.
    exit /b 1
)
call ".venv\Scripts\activate.bat"

echo [1/4] Installing build tools...
python -m pip install --upgrade pip pyinstaller || goto :fail
python -m pip install -r requirements.txt || goto :fail

echo [2/4] Building SafeFile.exe...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m PyInstaller --noconfirm --clean packaging\safefile.spec || goto :fail

echo [3/4] Building SafeFileMiniCloud.exe...
python -m PyInstaller --noconfirm --onefile --console --name SafeFileMiniCloud ^
        --icon "%CD%\safepoint\assets\safefile.ico" --paths "%CD%" --specpath build packaging\minicloud_entry.py || goto :fail

echo [4/4] Creating the installer...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do (
    if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    echo.
    echo Inno Setup 6 was not found, so no installer was made.
    echo Install it free from https://jrsoftware.org/isinfo.php and run build.bat again.
    echo The app itself is ready to test: dist\SafeFile\SafeFile.exe
    exit /b 0
)
for /f %%v in ('python -c "import safepoint; print(safepoint.__version__)"') do set "VERSION=%%v"
"%ISCC%" /DMyAppVersion=%VERSION% packaging\installer.iss || goto :fail

echo.
echo Done. Installer: installer_output\SafeFile-Setup-%VERSION%.exe
exit /b 0

:fail
echo.
echo Build failed. Scroll up for the first error message.
exit /b 1
