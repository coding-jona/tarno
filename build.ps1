# build.ps1 - Vollständiger Automatisierungs-Build für Tarno Mesh
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot

Write-Host "=== 1/3: WinUI 3 App publishen ===" -ForegroundColor Cyan
dotnet publish "$ProjectRoot\src\TARNO.UI\TARNO.UI.csproj" `
    -c Release `
    -r win-x64 `
    --self-contained true `
    -p:Platform=x64

Write-Host "`n=== 2/3: PyInstaller Bundle erstellen ===" -ForegroundColor Cyan
if (Test-Path "$ProjectRoot\build") { Remove-Item -Recurse -Force "$ProjectRoot\build" }
if (Test-Path "$ProjectRoot\dist") { Remove-Item -Recurse -Force "$ProjectRoot\dist" }

pyinstaller --noconfirm "$ProjectRoot\Tarno Mesh.spec"

Write-Host "`n=== 3/3: Windows Installer generieren (Inno Setup) ===" -ForegroundColor Cyan
$innoCompiler = "C:\Users\jonag\AppData\Local\Programs\Inno Setup 6\ISCC.exe"

if (Test-Path $innoCompiler) {
    & $innoCompiler "$ProjectRoot\setup.iss"
    Write-Host "`n✅ Fertig! Der Installer wurde erfolgreich generiert." -ForegroundColor Green
} else {
    Write-Host "`n⚠️ Inno Setup Compiler nicht gefunden unter: $innoCompiler" -ForegroundColor Yellow
    Write-Host "Das PyInstaller-Bundle in 'dist\Tarno Mesh' ist trotzdem einsatzbereit." -ForegroundColor Green
}