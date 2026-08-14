"""Command implementations for tarno_shell: run, logs, loaders"""
import csv
import sys
import sqlite3
import logging
from pathlib import Path
from .config import load_config
from .utils import get_log_path

LOG = logging.getLogger("tarno_shell.commands")


def run(config_path=None, target='stdout'):
    cfg = load_config(config_path) if config_path else {}
    source = cfg.get('source', {})
    src_path = source.get('path', 'samples/sample_input.csv')
    batch_size = cfg.get('batch_size', 1000)

    p = Path(src_path)
    if not p.exists():
        print(f"Source file not found: {p}")
        return

    if target.startswith('sqlite://'):
        db_path = target.split('sqlite:///')[-1]
        _run_to_sqlite(p, db_path, batch_size)
    else:
        _run_to_stdout(p, batch_size)


def _run_to_stdout(path: Path, batch_size: int):
    with path.open('r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        count = 0
        for row in reader:
            transformed = _transform_row(row)
            print(transformed)
            count += 1
            if count >= batch_size:
                break
    LOG.info(f"Run finished: output {count} rows to stdout")


def _run_to_sqlite(path: Path, db_path: str, batch_size: int):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # simple table
    cur.execute('CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT)')
    count = 0
    with path.open('r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            transformed = _transform_row(row)
            cur.execute('INSERT INTO samples (data) VALUES (?)', (str(transformed),))
            count += 1
            if count >= batch_size:
                break
    conn.commit()
    conn.close()
    LOG.info(f"Run finished: inserted {count} rows into {db_path}")


def _transform_row(row: dict) -> dict:
    # simple normalization: strip whitespace and lower-case string fields
    out = {}
    for k, v in row.items():
        if isinstance(v, str):
            out[k] = v.strip()
        else:
            out[k] = v
    return out


def show_logs(tail: int = 200):
    logp = get_log_path()
    if not logp.exists():
        print("No log file yet")
        return
    with logp.open('r', encoding='utf-8') as fh:
        lines = fh.readlines()
        for line in lines[-tail:]:
            print(line.rstrip())
