# build.ps1 - Vollständiger Automatisierungs-Build für Tarno Mesh
# Liegt unter workspace/installer/, also zwei Ebenen unterm Repo-Root.
$ErrorActionPreference = "Stop"

$InstallerDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $InstallerDir)

Write-Host "=== 1/3: WinUI 3 App publishen ===" -ForegroundColor Cyan
dotnet publish "$ProjectRoot\src\TARNO.UI\TARNO.UI.csproj" `
    -c Release `
    -r win-x64 `
    --self-contained true `
    -p:Platform=x64

Write-Host "`n=== 2/3: PyInstaller Bundle erstellen ===" -ForegroundColor Cyan
if (Test-Path "$InstallerDir\build") { Remove-Item -Recurse -Force "$InstallerDir\build" }
if (Test-Path "$InstallerDir\dist") { Remove-Item -Recurse -Force "$InstallerDir\dist" }

Push-Location $InstallerDir
try {
    pyinstaller --noconfirm "$InstallerDir\Tarno Mesh.spec"
}
finally {
    Pop-Location
}

Write-Host "`n=== 3/3: Windows Installer generieren (Inno Setup) ===" -ForegroundColor Cyan
$innoCompiler = "C:\Users\jonag\AppData\Local\Programs\Inno Setup 6\ISCC.exe"

if (Test-Path $innoCompiler) {
    & $innoCompiler "$InstallerDir\setup.iss"
    Write-Host "`n✅ Fertig! Der Installer wurde erfolgreich generiert." -ForegroundColor Green
} else {
    Write-Host "`n⚠️ Inno Setup Compiler nicht gefunden unter: $innoCompiler" -ForegroundColor Yellow
    Write-Host "Das PyInstaller-Bundle in 'workspace\installer\dist\Tarno Mesh' ist trotzdem einsatzbereit." -ForegroundColor Green
}