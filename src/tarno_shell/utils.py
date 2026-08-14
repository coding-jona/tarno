"""Utilities: logging, pidfile path helpers"""
import os
from pathlib import Path
import logging
import platform

APP_NAME = "tarno"


def base_data_dir() -> Path:
    if platform.system() == 'Windows':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'TARNO'
    else:
        return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'tarno'


def ensure_dirs():
    d = base_data_dir()
    (d / 'logs').mkdir(parents=True, exist_ok=True)
    (d / 'run').mkdir(parents=True, exist_ok=True)


def pidfile_path() -> str:
    d = base_data_dir() / 'run'
    return str(d / 'tarno_shell.pid')


def get_log_path() -> Path:
    return base_data_dir() / 'logs' / 'tarno_shell.log'


def setup_logging():
    ensure_dirs()
    logp = get_log_path()
    logging.basicConfig(level=logging.INFO, filename=str(logp), format='%(asctime)s %(levelname)s %(message)s')
