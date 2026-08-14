[Setup]
AppName=Tarno Mesh
AppVersion=1.2.0

; Herausgeber & Firmen-Metadaten
AppPublisher=coding-jona, Dr-Deep
VersionInfoCompany=Tarno AI
VersionInfoCopyright=Copyright (C) 2026 Tarno AI (coding-jona, Dr-Deep)
VersionInfoDescription=Tarno Mesh Application
VersionInfoVersion=1.2.0

; Relative Pfade zum Repo-Root
SetupIconFile=src\TARNO.UI\Assets\app.ico
OutputDir=Output
OutputBaseFilename=Tarno_Mesh_Setup_v1.2.0

; Installations-Pfade auf dem Ziel-System
DefaultDirName={autopf}\Tarno Mesh
DefaultGroupName=Tarno Mesh
UninstallDisplayIcon={app}\Tarno Mesh.exe

Compression=lzma2/ultra64
SolidCompression=yes
SetupLogging=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Relativer Pfad zum Build-Ordner von PyInstaller
Source: "dist\Tarno Mesh\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tarno Mesh"; Filename: "{app}\Tarno Mesh.exe"
Name: "{group}\Tarno Mesh Deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Tarno Mesh"; Filename: "{app}\Tarno Mesh.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Tarno Mesh.exe"; Description: "{cm:LaunchProgram,Tarno Mesh}"; Flags: nowait postinstall skipifsilent