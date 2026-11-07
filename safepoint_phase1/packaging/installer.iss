; Inno Setup script for SafeFile. Build with build.bat (or open this file in Inno Setup and press Compile).
#define MyAppName "SafeFile"
#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif

[Setup]
AppId={{1DBDC133-6B67-4456-A548-F62129A3A2FD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; installs for the current user only: no administrator rights needed
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\installer_output
OutputBaseFilename=SafeFile-Setup-{#MyAppVersion}
SetupIconFile=..\safepoint\assets\safefile.ico
UninstallDisplayIcon={app}\SafeFile.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start SafeFile when Windows starts (opens in the tray)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\SafeFile\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\dist\SafeFileMiniCloud.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\SafeFile.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\SafeFile.exe"; Tasks: desktopicon

[Registry]
; same value SafeFile's own Settings switch writes, so the two stay in sync; removed on uninstall
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SafeFile"; ValueData: """{app}\SafeFile.exe"" --minimized"; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\SafeFile.exe"; Description: "Launch SafeFile"; Flags: nowait postinstall skipifsilent

; Your backups and settings live in %LOCALAPPDATA%\SafeFile and are NOT deleted when you uninstall.
