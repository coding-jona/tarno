"""CLI entrypoint for tarno_shell (tarno shell / terminal variant)

Basic subcommands: run, start, stop, status, logs
"""
import argparse
import sys
from . import commands
from .runner import Runner


def build_parser():
    parser = argparse.ArgumentParser(prog="tarno_shell")
    sub = parser.add_subparsers(dest="cmd")

    parser_run = sub.add_parser("run", help="Run a one-shot ETL task")
    parser_run.add_argument("--config", "-c", required=False, help="Path to config YAML (optional)")
    parser_run.add_argument("--target", "-t", default="stdout", help="Target: stdout or sqlite:///<path>")

    parser_start = sub.add_parser("start", help="Start as a long-running runner")
    parser_start.add_argument("--daemon", action="store_true", help="Daemonize (Unix only)")
    parser_start.add_argument("--config", "-c", required=False, help="Path to config YAML (optional)")

    parser_stop = sub.add_parser("stop", help="Stop running runner")
    parser_status = sub.add_parser("status", help="Show runner status")

    parser_logs = sub.add_parser("logs", help="Show logs")
    parser_logs.add_argument("--tail", "-n", type=int, default=200, help="Tail lines")

    return parser


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    runner = Runner()

    if args.cmd == "run":
        commands.run(config_path=args.config, target=args.target)
    elif args.cmd == "start":
        runner.start(config_path=args.config, daemon=args.daemon)
    elif args.cmd == "stop":
        runner.stop()
    elif args.cmd == "status":
        runner.status()
    elif args.cmd == "logs":
        commands.show_logs(tail=args.tail)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
