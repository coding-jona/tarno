<#
.SYNOPSIS
    Verifiziert TARNO.UI-Build und Python-Tests.
.DESCRIPTION
    Führt sequentiell aus:
      1. dotnet build src/TARNO.UI/TARNO.UI.csproj
      2. python -m unittest discover -s tests
    Bei einem Fehler wird sofort abgebrochen.
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Step-Build {
    Write-Host "`n[1/2] dotnet build TARNO.UI ..." -ForegroundColor Cyan
    $csproj = Join-Path (Join-Path (Join-Path $root 'src') 'TARNO.UI') 'TARNO.UI.csproj'
    dotnet build $csproj -c Debug -p:Platform=x64 -v q --nologo
    if ($LASTEXITCODE -ne 0) { throw "Build failed with exit code $LASTEXITCODE" }
    Write-Host "Build OK." -ForegroundColor Green
}

function Step-Tests {
    Write-Host "`n[2/2] Python unit tests ..." -ForegroundColor Cyan
    $env:PYTHONPATH = $root
    python -m unittest discover -s (Join-Path $root 'tests') -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed with exit code $LASTEXITCODE" }
    Write-Host "Tests OK." -ForegroundColor Green
}

Push-Location $root
try {
    if (-not $SkipBuild) { Step-Build }
    if (-not $SkipTests) { Step-Tests }
    Write-Host "`nAll verification steps passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
