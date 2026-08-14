# PowerShell helper to create venv and run the shell
$Root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $Root '.venv'
if (-not (Test-Path $venv)) {
    python -m venv $venv
}
$activate = Join-Path $venv 'Scripts' 'Activate.ps1'
. $activate
pip install --upgrade pip
pip install pyyaml
python -m tarno_shell run --config "$(Join-Path $Root 'samples' 'sample_config.yaml')"
