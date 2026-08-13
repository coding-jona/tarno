<#
.SYNOPSIS
    Baut den TARNO-Installer fuer Windows inkl. Python-Backend und WinUI 3-Frontend.
.DESCRIPTION
    Schritte:
      1. Python-Tests
      2. Secret-Scan (verhindert versehentlich eingebettete API-Keys im Build)
      3. dotnet build TARNO.UI
      4. PyInstaller fuer Python-Backend
      5. Kopiert Frontend-Assets
      6. NSIS-Installer
    Parameter:
      -Configuration: Debug oder Release (Default: Debug)
      -SkipTests: Python-Tests ueberspringen
      -SkipBuild: Build-Schritte ueberspringen
      -SkipInstaller: NSIS-Installer nicht erzeugen
#>
[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Debug',
    [switch]$SkipTests,
    [switch]$SkipBuild,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

# KERNFIX: 'python' zeigte auf das System-Python (aktuell 3.14), nicht auf
# das Projekt-venv (.venv, Python 3.12) - genau die Python-Version, wegen der
# diese Session schon einmal ein eigenes venv angelegt hat, weil pygame/
# pyaudio & Co. unter 3.14 nicht liefen (siehe requirements.txt-Historie).
# Dadurch schlugen die Tests mit "module 'tarno.voice' has no attribute
# 'audio_stream'" fehl (pyaudio-Import in dieser Python-Version kaputt/
# fehlend) UND PyInstaller haette (waere es ueberhaupt fuer 3.14 installiert
# gewesen) das Backend mit der falschen Python-Version gepackt. Explizit auf
# das venv zeigen, damit Tests UND PyInstaller-Build dieselbe, tatsaechlich
# funktionierende Umgebung nutzen wie der taegliche Backend-Betrieb.
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    throw "Projekt-venv nicht gefunden unter $venvPython - siehe README zum Einrichten (Python 3.12, nicht System-Python)."
}
$python = $venvPython
$dotnet = 'dotnet'
$nsis = 'C:\Program Files (x86)\NSIS\makensis.exe'

$csproj = Join-Path $root (Join-Path 'src' (Join-Path 'TARNO.UI' 'TARNO.UI.csproj'))
$spec = Join-Path $root 'tarno.spec'
$nsisScript = Join-Path $root 'TARNO_Installer.nsi'

$distDir = Join-Path $root 'dist'
$installerDist = Join-Path $distDir 'TARNO_Package'
$pyinstallerOutput = Join-Path $distDir 'tarno_backend'

function Step-Tests {
    Write-Host "`n[1/5] Python-Tests ..." -ForegroundColor Cyan
    $env:PYTHONPATH = $root
    & $python -m unittest discover -s (Join-Path $root 'tests') -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE" }
    Write-Host "Tests OK." -ForegroundColor Green
}

function Step-SecretScan {
    Write-Host "`n[2/6] Secret-Scan ..." -ForegroundColor Cyan
    $env:PYTHONPATH = $root
    & $python -c "from tarno.security.build_secret_scan import verify_no_secrets; from pathlib import Path; verify_no_secrets(Path(r'$root'))"
    if ($LASTEXITCODE -ne 0) { throw "Secret scan failed with exit code $LASTEXITCODE - moeglicher API-Key-Leak im Quellcode" }
    Write-Host "Secret-Scan OK." -ForegroundColor Green
}

function Step-DotNetBuild {
    Write-Host "`n[3/6] dotnet publish TARNO.UI ($Configuration) ..." -ForegroundColor Cyan
    # The project is configured for self-contained deployment
    # (WindowsAppSDKSelfContained=true, RuntimeIdentifiers in the csproj) -
    # a plain `dotnet build` produces an apphost that still expects a private
    # runtime copy next to the exe but never actually copies one in, so the
    # installed app fails with ".NET location: ...\UI\ - No frameworks were
    # found" even though the shared runtime is installed system-wide (found
    # live: this broke every packaged install this session). `dotnet publish`
    # with an explicit RID + --self-contained actually produces a real,
    # relocatable standalone deployment.
    & $dotnet publish $csproj -c $Configuration -p:Platform=x64 -r win-x64 --self-contained true -v q --nologo
    if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed with exit code $LASTEXITCODE" }
    Write-Host "dotnet publish OK." -ForegroundColor Green
}

function Step-PyInstaller {
    Write-Host "`n[4/6] PyInstaller Python-Backend ..." -ForegroundColor Cyan
    Push-Location $root
    try {
        & $python -m PyInstaller $spec --noconfirm --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build\pyinstaller')
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }
    Write-Host "PyInstaller OK." -ForegroundColor Green
}

function Step-AssembleFiles {
    Write-Host "`n[5/6] Installer-Dateien zusammenstellen ..." -ForegroundColor Cyan
    if (Test-Path $installerDist) {
        Remove-Item -Recurse -Force $installerDist
    }
    New-Item -ItemType Directory -Path $installerDist -Force | Out-Null

    # Python-Backend
    $pyDir = Join-Path $pyinstallerOutput 'tarno'
    if (-not (Test-Path $pyDir)) {
        $pyDir = $pyinstallerOutput
    }
    if (-not (Test-Path $pyDir)) {
        throw "PyInstaller output not found at $pyinstallerOutput"
    }
    Write-Host "Kopiere Python-Backend von $pyDir ..." -ForegroundColor DarkGray
    $pyFiles = Get-ChildItem -Path $pyDir -Force
    if ($pyFiles.Count -eq 0) {
        throw "PyInstaller output directory $pyDir is empty"
    }
    Copy-Item -Path (Join-Path $pyDir '*') -Destination $installerDist -Recurse -Force

    # WinUI 3 Frontend - dotnet publish (see Step-DotNetBuild) puts the
    # self-contained, relocatable output in a RID-specific "publish" subfolder,
    # not directly under the TFM folder like `dotnet build` does.
    $uiOutput = Join-Path $root (Join-Path 'src' (Join-Path 'TARNO.UI' (Join-Path 'bin' (Join-Path 'x64' (Join-Path $Configuration (Join-Path 'net8.0-windows10.0.19041.0' (Join-Path 'win-x64' 'publish')))))))
    if (-not (Test-Path $uiOutput)) {
        throw "WinUI 3 build output not found at $uiOutput"
    }
    $uiDest = Join-Path $installerDist 'UI'
    New-Item -ItemType Directory -Path $uiDest -Force | Out-Null
    Copy-Item -Path "$uiOutput\*" -Destination $uiDest -Recurse -Force

    # Runtime installers bundled for offline install on fresh machines.
    # WebView2 is required for the provider API-key onboarding dialog
    # (ProviderLoginDialog). The NSIS installer downloads the Microsoft
    # Evergreen Bootstrapper at install time; internet is required.
    $runtimesDir = Join-Path $installerDist 'runtimes'
    New-Item -ItemType Directory -Path $runtimesDir -Force | Out-Null
    $dotnetUrl = 'https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/8.0.15/windowsdesktop-runtime-8.0.15-win-x64.exe'
    $vcredistUrl = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
    $dotnetOut = Join-Path $runtimesDir 'dotnet8-runtime.exe'
    $vcredistOut = Join-Path $runtimesDir 'vcredist-x64.exe'

    if (-not (Test-Path $dotnetOut)) {
        Invoke-WebRequest -Uri $dotnetUrl -OutFile $dotnetOut -UseBasicParsing
    }
    if (-not (Test-Path $vcredistOut)) {
        Invoke-WebRequest -Uri $vcredistUrl -OutFile $vcredistOut -UseBasicParsing
    }

    # A simple launcher batch is kept for manual testing; NSIS creates the real shortcut.
    @'
@echo off
start "" "%~dp0UI\TARNO.UI.exe"
'@ | Set-Content -Path (Join-Path $installerDist 'TARNO.bat') -Encoding ASCII
    Write-Host "Dateien zusammengestellt unter $installerDist" -ForegroundColor Green
}

function Step-Installer {
    Write-Host "`n[6/6] NSIS-Installer bauen ..." -ForegroundColor Cyan
    if (-not (Test-Path $nsisScript)) {
        throw "NSIS script not found at $nsisScript"
    }
    if (-not (Test-Path $nsis)) {
        throw "NSIS compiler not found at $nsis. Install NSIS from https://nsis.sourceforge.io"
    }
    & $nsis $nsisScript
    if ($LASTEXITCODE -ne 0) { throw "NSIS build failed with exit code $LASTEXITCODE" }
    Write-Host "Installer OK." -ForegroundColor Green
}

try {
    if (-not $SkipTests) { Step-Tests }
    Step-SecretScan
    if (-not $SkipBuild) {
        Step-DotNetBuild
        Step-PyInstaller
    }
    Step-AssembleFiles
    if (-not $SkipInstaller) { Step-Installer }
    Write-Host "`nAlle Installer-Schritte erfolgreich." -ForegroundColor Green
}
catch {
    Write-Host "`nFEHLER: $_" -ForegroundColor Red
    exit 1
}
