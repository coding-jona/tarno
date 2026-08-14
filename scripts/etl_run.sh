#!/bin/sh
set -e
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT_DIR/.venv/bin/activate" 2>/dev/null || true
if [ ! -d "$ROOT_DIR/.venv" ]; then
  python3 -m venv "$ROOT_DIR/.venv"
  . "$ROOT_DIR/.venv/bin/activate"
  pip install --upgrade pip
  pip install pyyaml
fi
. "$ROOT_DIR/.venv/bin/activate"
python -m tarno_shell run --config "$ROOT_DIR/samples/sample_config.yaml"
