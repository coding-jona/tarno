[Setup]
; Eindeutige, feste Kennung der Anwendung fuer Inno Setup - ohne AppId
; verwendet Inno Setup implizit AppName als Registry-/Upgrade-Schluessel;
; das verhindert saubere Upgrade-Erkennung sobald sich AppName mal aendert
; und ist ohnehin nicht Best Practice. Einmal generiert, MUSS diese GUID in
; allen zukuenftigen Versionen unveraendert bleiben, sonst behandelt der
; Windows-Installer ein Upgrade als komplett neue, parallele Installation.
AppId={{09655D48-F9BF-4D34-AF9B-AAE21A36BF4A}
AppName=Tarno Mesh
AppVersion=1.2.0

; Herausgeber & Firmen-Metadaten
AppPublisher=coding-jona, Dr-Deep
VersionInfoCompany=Tarno AI
VersionInfoCopyright=Copyright (C) 2026 Tarno AI (coding-jona, Dr-Deep)
VersionInfoDescription=Tarno Mesh Application
VersionInfoVersion=1.2.0

; Diese Datei liegt unter workspace\installer\, also zwei Ebenen unterm
; Repo-Root - Pfade zu Repo-weiten Quellen (src\...) brauchen deshalb ..\..\.
SetupIconFile=..\..\src\TARNO.UI\Assets\app.ico
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
; Relativer Pfad zum Build-Ordner von PyInstaller (Python-Backend)
Source: "dist\Tarno Mesh\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; KERNFIX: Der Installer band bisher NUR das PyInstaller-Backend ein - die
; WinUI-3-Frontend-EXE (TARNO.UI.exe, per "dotnet publish" erzeugt) wurde
; nie mitgepackt. winui_launcher.py._default_exe_path() sucht
; "TARNO.UI.exe" im selben Ordner wie "Tarno Mesh.exe"; ohne diese Zeile
; findet sie die installierte App nie, meldet "WinUI-Exe nicht gefunden"
; und beendet sich sofort wieder - genau das live beobachtete
; "startet, dann direkt wieder weg"-Verhalten nach der Installation.
; Pfad muss zu "dotnet publish ... -r win-x64 --self-contained true"
; passen (siehe build.ps1). ..\..\ da diese Datei unter workspace\installer\
; liegt, src\ aber am Repo-Root.
Source: "..\..\src\TARNO.UI\bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tarno Mesh"; Filename: "{app}\Tarno Mesh.exe"
Name: "{group}\Tarno Mesh Deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Tarno Mesh"; Filename: "{app}\Tarno Mesh.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Tarno Mesh.exe"; Description: "{cm:LaunchProgram,Tarno Mesh}"; Flags: nowait postinstall skipifsilent