# Tarno Shell

This branch adds a minimal terminal/CLI starter for Tarno (tarno_shell).

Quickstart

- Create a virtualenv and install PyYAML:
  python3 -m venv .venv
  source .venv/bin/activate
  pip install pyyaml

- Run the sample ETL (reads samples/sample_input.csv and writes to stdout):
  python -m tarno_shell run --config samples/sample_config.yaml

- Start the runner in foreground:
  python -m tarno_shell start

- Show logs:
  python -m tarno_shell logs
