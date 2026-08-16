#define MyAppName "B2B Serv"
#define MyAppVersion "0.3.1"
#define MyAppPublisher "nutelex"
#define MyAppExeName "B2B Serv.exe"

[Setup]
AppId={{6A7BF5C5-8E63-4E2B-9C72-7D4B3B6D0F91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer-dist
OutputBaseFilename=B2B-Serv-Installer
SetupIconFile=app-icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
UninstallFilesDir={app}\_setup

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\\French.isl"

[Files]
Source: "dist\\B2B Serv\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app-icon.ico"; DestDir: "{app}\\resources"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; IconFilename: "{app}\\resources\\app-icon.ico"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; IconFilename: "{app}\\resources\\app-icon.ico"

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent
