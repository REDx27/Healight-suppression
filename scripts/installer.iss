#define MyAppName "GlareTracker"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Glare Tracking Project"
#define MyAppExeName "GlareTracker.exe"

[Setup]
AppId={{B7A8B6F4-3E08-4A59-9C75-8A4C2F0D7E11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer-output
OutputBaseFilename=GlareTracker-Setup
UninstallDisplayName={#MyAppName}
PrivilegesRequired=lowest
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\glaretracker-icon.ico

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent