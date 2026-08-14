"""Simple runner / daemon wrapper for tarno_shell

Provides start/stop/status via a pidfile and simple process handling.
"""
import os
import sys
import time
import signal
import logging
import platform
from pathlib import Path
from .utils import ensure_dirs, pidfile_path
from .commands import run

LOG = logging.getLogger("tarno_shell.runner")

class Runner:
    def __init__(self):
        self._pidfile = pidfile_path()
        ensure_dirs()

    def start(self, config_path=None, daemon=False):
        if self._is_running():
            print("Runner already running.")
            return
        if daemon and platform.system() != 'Windows':
            # Unix daemonize
            pid = os.fork()
            if pid > 0:
                # parent
                print(f"Started daemon with pid {pid}")
                return
            # child
            os.setsid()
            pid2 = os.fork()
            if pid2 > 0:
                os._exit(0)
            # redirect stdio to /dev/null
            sys.stdout.flush()
            sys.stderr.flush()
            with open('/dev/null', 'r') as devnull:
                os.dup2(devnull.fileno(), sys.stdin.fileno())
            with open('/dev/null', 'a+') as devnull:
                os.dup2(devnull.fileno(), sys.stdout.fileno())
                os.dup2(devnull.fileno(), sys.stderr.fileno())
            # write pidfile
            Path(self._pidfile).write_text(str(os.getpid()))
            # run
            self._run_loop(config_path)
        else:
            # foreground
            Path(self._pidfile).write_text(str(os.getpid()))
            try:
                self._run_loop(config_path)
            finally:
                self._cleanup()

    def _run_loop(self, config_path):
        LOG.info("Runner starting main loop")
        try:
            while True:
                run(config_path=config_path, target='stdout')
                # one minute interval between runs
                time.sleep(60)
        except KeyboardInterrupt:
            LOG.info("Runner interrupted")
        except Exception as e:
            LOG.exception(f"Runner exception: {e}")

    def stop(self):
        if not self._is_running():
            print("No runner is running.")
            return
        pid = int(Path(self._pidfile).read_text())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to {pid}")
        except Exception as e:
            print(f"Could not stop process {pid}: {e}")
        finally:
            self._cleanup()

    def status(self):
        if self._is_running():
            pid = int(Path(self._pidfile).read_text())
            print(f"Runner is running (pid {pid})")
        else:
            print("Runner is not running")

    def _is_running(self):
        if not Path(self._pidfile).exists():
            return False
        try:
            pid = int(Path(self._pidfile).read_text())
        except Exception:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _cleanup(self):
        try:
            if Path(self._pidfile).exists():
                Path(self._pidfile).unlink()
        except Exception:
            pass
