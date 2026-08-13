"""Entry point: `python -m tarno.grpc [--mock] [--port 50051]`."""

from __future__ import annotations

import argparse
import asyncio
import logging

from tarno.grpc.server import run_grpc_server


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TARNO gRPC backend for the WinUI frontend")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the mock engine instead of a real LLM provider (no API key needed).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50051,
        help="gRPC port to listen on (default: 50051).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (default: INFO).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    asyncio.run(run_grpc_server(port=args.port, mock=args.mock))


if __name__ == "__main__":
    main()
