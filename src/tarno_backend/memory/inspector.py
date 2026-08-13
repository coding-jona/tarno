"""CLI to inspect and correct TARNO's long-term memory (Block 4, Phase 37).

Usage:
    py -3.12 -m tarno.memory.inspector list
    py -3.12 -m tarno.memory.inspector export ~/tarno_memory_export.json
    py -3.12 -m tarno.memory.inspector import ~/tarno_memory_export.json

Edit the exported JSON file by hand (correct a wrong fact, delete an entry
you don't want remembered, fix a typo), then import it back - facts and
preferences are upserted by key, episodes are only added if not already
present, so re-importing the same file repeatedly is safe.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tarno_backend.core.config import TarnoConfig
from tarno_backend.memory.store import MemoryStore


def _open_store(config: TarnoConfig) -> MemoryStore:
    memory_path = Path(config.memory.storage_dir).expanduser() / "memory.db"
    return MemoryStore(memory_path)


def _cmd_list(store: MemoryStore) -> None:
    facts = store.search_facts("", limit=1000)
    episodes = store.get_recent_episodes(limit=1000)
    print(f"Fakten ({len(facts)}):")
    for f in facts:
        print(f"  - {f.key}: {f.value}  [{f.source}, aktualisiert {f.updated_at:%Y-%m-%d}]")
    print(f"\nEpisoden ({len(episodes)}):")
    for e in episodes:
        tags = ", ".join(e.tags) if e.tags else "-"
        print(f"  - {e.created_at:%Y-%m-%d %H:%M}  [{tags}]  {e.summary}")


def _cmd_export(store: MemoryStore, path: str) -> None:
    count = store.export_to_json(path)
    print(f"{count} Einträge exportiert nach {Path(path).expanduser()}")


def _cmd_import(store: MemoryStore, path: str) -> None:
    count = store.import_from_json(path)
    print(f"{count} Einträge importiert aus {Path(path).expanduser()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Alle Fakten und Episoden auflisten")

    export_parser = subparsers.add_parser("export", help="Gedächtnis als JSON exportieren")
    export_parser.add_argument("path", help="Zielpfad für die JSON-Datei")

    import_parser = subparsers.add_parser("import", help="JSON-Datei ins Gedächtnis übernehmen")
    import_parser.add_argument("path", help="Quellpfad der JSON-Datei")

    args = parser.parse_args(argv)
    config = TarnoConfig.load()
    store = _open_store(config)

    if args.command == "list":
        _cmd_list(store)
    elif args.command == "export":
        _cmd_export(store, args.path)
    elif args.command == "import":
        _cmd_import(store, args.path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
