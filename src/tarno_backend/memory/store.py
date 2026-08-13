"""SQLite-backed memory store for facts, episodes and preferences."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from tarno_backend.memory.embeddings import blob_to_vector as _blob_to_vector
from tarno_backend.memory.embeddings import cosine_similarity as _cosine_similarity
from tarno_backend.memory.embeddings import vector_to_blob as _vector_to_blob

log = logging.getLogger(__name__)


@dataclass
class MemoryFact:
    id: int | None
    key: str
    value: str
    source: str
    created_at: datetime
    updated_at: datetime


@dataclass
class MemoryEpisode:
    id: int | None
    summary: str
    tags: list[str]
    created_at: datetime


class MemoryStore:
    """Persistent SQLite store for TARNO memory.

    Each thread gets its own SQLite connection via ``threading.local`` so that
    cross-thread use of the same connection object is impossible. This avoids the
    "SQLite objects created in a thread can only be used in that same thread"
    error while still allowing the same ``MemoryStore`` instance to be used from
    multiple threads.
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        value TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        summary TEXT NOT NULL,
        tags TEXT NOT NULL DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        value TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.5,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);
    CREATE INDEX IF NOT EXISTS idx_episodes_tags ON episodes(tags);
    CREATE INDEX IF NOT EXISTS idx_preferences_key ON preferences(key);
    """

    def __init__(self, db_path: Path | str = "~/.tarno/memory/memory.db") -> None:
        self._path = str(Path(db_path).expanduser()) if db_path != ":memory:" else ":memory:"
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # SQLite's shared-cache in-memory URI is keyed by name - a fixed name
        # here would mean every MemoryStore(":memory:") instance in the whole
        # process shares ONE database, not just threads within THIS instance
        # (found live: unrelated tests' small test embeddings leaked into a
        # different test's real 384-dim query, "shapes (384,) and (2,) not
        # aligned"). A per-instance unique name keeps the intended
        # cross-THREAD sharing while isolating separate instances.
        self._memory_uri = f"file:memdb_{uuid.uuid4().hex}?mode=memory&cache=shared"
        self._lock = threading.Lock()
        self._connections_lock = threading.Lock()
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a SQLite connection bound to the current thread."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            if self._path == ":memory:":
                # Use a shared in-memory database so separate per-thread
                # connections still see the same tables and data.
                conn = sqlite3.connect(
                    self._memory_uri, uri=True, check_same_thread=False
                )
            else:
                conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
            with self._connections_lock:
                self._connections.append(conn)
        return conn

    def _ensure_schema(self) -> None:
        with self._lock:
            self._get_conn().executescript(self._SCHEMA)
            self._migrate_embedding_columns()
        log.debug("Memory-Schema in %s geprüft", self._path)

    def _migrate_embedding_columns(self) -> None:
        """Add the 'embedding' BLOB column to facts/episodes if missing.

        Block 4 (Phase 31): existing databases created before semantic search
        was added won't have this column - SQLite has no
        "ADD COLUMN IF NOT EXISTS", so check PRAGMA table_info() first.
        """
        conn = self._get_conn()
        for table in ("facts", "episodes"):
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "embedding" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN embedding BLOB")
                log.info("Migration: 'embedding'-Spalte zu %s hinzugefügt", table)
        conn.commit()

    def close(self) -> None:
        """Close all SQLite connections opened by this store."""
        with self._connections_lock:
            connections = self._connections[:]
            self._connections.clear()
        for conn in connections:
            try:
                conn.close()
            except Exception:
                pass

    def save_fact(
        self, key: str, value: str, source: str = "user", embedding: np.ndarray | None = None,
    ) -> None:
        now = datetime.now().isoformat()
        blob = _vector_to_blob(embedding) if embedding is not None else None
        with self._lock:
            with self._get_conn():
                self._get_conn().execute(
                    """
                    INSERT INTO facts (key, value, source, created_at, updated_at, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        source = excluded.source,
                        updated_at = excluded.updated_at,
                        embedding = COALESCE(excluded.embedding, facts.embedding)
                    """,
                    (key, value, source, now, now, blob),
                )

    def get_fact(self, key: str) -> MemoryFact | None:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM facts WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return MemoryFact(
            id=row["id"],
            key=row["key"],
            value=row["value"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def search_facts(self, query: str, limit: int = 10) -> list[MemoryFact]:
        pattern = f"%{query}%"
        with self._lock:
            rows = self._get_conn().execute(
                """
                SELECT * FROM facts
                WHERE key LIKE ? OR value LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
        return [
            MemoryFact(
                id=r["id"],
                key=r["key"],
                value=r["value"],
                source=r["source"],
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            for r in rows
        ]

    def search_facts_by_vector(
        self, query_vector: np.ndarray, limit: int = 10, min_similarity: float = 0.3,
    ) -> list[tuple[MemoryFact, float]]:
        """Semantic search over facts with a stored embedding (Block 4, Phase 31).

        Brute-force cosine similarity - fine at the scale of a personal
        assistant's fact store (hundreds to low thousands of rows), avoids
        needing a real vector index/ANN library. Facts saved before
        embeddings existed (embedding IS NULL) are simply not returned here;
        callers should combine this with keyword search for full coverage.
        """
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM facts WHERE embedding IS NOT NULL"
            ).fetchall()

        scored: list[tuple[MemoryFact, float]] = []
        for row in rows:
            similarity = _cosine_similarity(query_vector, _blob_to_vector(row["embedding"]))
            if similarity < min_similarity:
                continue
            scored.append((
                MemoryFact(
                    id=row["id"], key=row["key"], value=row["value"], source=row["source"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                ),
                similarity,
            ))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    def search_episodes_by_vector(
        self, query_vector: np.ndarray, limit: int = 10, min_similarity: float = 0.3,
    ) -> list[tuple[MemoryEpisode, float]]:
        """Semantic search over episodes with a stored embedding. See
        search_facts_by_vector() for the brute-force cosine-similarity rationale."""
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM episodes WHERE embedding IS NOT NULL"
            ).fetchall()

        scored: list[tuple[MemoryEpisode, float]] = []
        for row in rows:
            similarity = _cosine_similarity(query_vector, _blob_to_vector(row["embedding"]))
            if similarity < min_similarity:
                continue
            scored.append((
                MemoryEpisode(
                    id=row["id"], summary=row["summary"], tags=json.loads(row["tags"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                ),
                similarity,
            ))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    def save_episode(
        self, summary: str, tags: list[str] | None = None, embedding: np.ndarray | None = None,
    ) -> int:
        tags = tags or []
        now = datetime.now().isoformat()
        blob = _vector_to_blob(embedding) if embedding is not None else None
        with self._lock:
            with self._get_conn():
                cur = self._get_conn().execute(
                    "INSERT INTO episodes (summary, tags, created_at, embedding) VALUES (?, ?, ?, ?)",
                    (summary, json.dumps(tags), now, blob),
                )
                return int(cur.lastrowid)

    def get_recent_episodes(self, limit: int = 10) -> list[MemoryEpisode]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            MemoryEpisode(
                id=r["id"],
                summary=r["summary"],
                tags=json.loads(r["tags"]),
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def set_preference(self, key: str, value: str, confidence: float = 0.5) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            with self._get_conn():
                self._get_conn().execute(
                    """
                    INSERT INTO preferences (key, value, confidence, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        confidence = excluded.confidence,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, confidence, now),
                )

    def get_preference(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM preferences WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "value": row["value"],
            "confidence": row["confidence"],
            "updated_at": row["updated_at"],
        }

    def delete_by_key(self, key: str) -> None:
        with self._lock:
            with self._get_conn():
                self._get_conn().execute("DELETE FROM facts WHERE key = ?", (key,))
                self._get_conn().execute("DELETE FROM preferences WHERE key = ?", (key,))

    def prune_stale(
        self, episode_max_age_days: int = 30, preference_min_confidence: float = 0.3,
    ) -> dict[str, int]:
        """Delete stale/low-value memory entries to keep the store clean
        (Block 4, Phase 35: "Relevanz-Erosion").

        - Episodes older than episode_max_age_days: one-off event logs (e.g.
          "checked the weather yesterday"), not durable facts - safe to purge
          once they're no longer recent enough to be conversationally relevant.
        - Preferences below preference_min_confidence: uncertain guesses that
          were never reinforced into higher confidence.

        Facts (name, wohnort, etc.) are deliberately NOT pruned here - they're
        durable identity/preference data, not the "one-off info" this phase
        targets, and a wrong prune there is costlier than a few stale rows
        lingering in facts.
        """
        cutoff = (datetime.now() - timedelta(days=episode_max_age_days)).isoformat()
        with self._lock:
            with self._get_conn():
                episodes_cur = self._get_conn().execute(
                    "DELETE FROM episodes WHERE created_at < ?", (cutoff,)
                )
                preferences_cur = self._get_conn().execute(
                    "DELETE FROM preferences WHERE confidence < ?", (preference_min_confidence,)
                )
        result = {
            "episodes_deleted": episodes_cur.rowcount,
            "preferences_deleted": preferences_cur.rowcount,
        }
        if result["episodes_deleted"] or result["preferences_deleted"]:
            log.info("Memory-Pruning: %s", result)
        return result

    def export_to_json(self, path: Path | str) -> int:
        """Dump facts/episodes/preferences to a human-readable JSON file
        (Block 4, Phase 37: manual inspection/correction interface).

        Embedding vectors are intentionally omitted (not human-editable,
        regenerated automatically on import) - only the fields a person would
        actually want to review or correct are included.
        """
        with self._lock:
            facts = self._get_conn().execute(
                "SELECT key, value, source, created_at, updated_at FROM facts ORDER BY key"
            ).fetchall()
            episodes = self._get_conn().execute(
                "SELECT summary, tags, created_at FROM episodes ORDER BY created_at DESC"
            ).fetchall()
            preferences = self._get_conn().execute(
                "SELECT key, value, confidence, updated_at FROM preferences ORDER BY key"
            ).fetchall()

        data = {
            "facts": [dict(r) for r in facts],
            "episodes": [{**dict(r), "tags": json.loads(r["tags"])} for r in episodes],
            "preferences": [dict(r) for r in preferences],
        }
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        total = len(data["facts"]) + len(data["episodes"]) + len(data["preferences"])
        log.info("Gedächtnis nach %s exportiert (%d Einträge)", out_path, total)
        return total

    def import_from_json(self, path: Path | str, recompute_embeddings: bool = True) -> int:
        """Re-apply a (possibly manually corrected) export from export_to_json().

        Facts and preferences are upserted by key (matching save_fact's/
        set_preference's own conflict handling). Episodes are only imported
        if they don't already exist (matched by exact summary+created_at) -
        re-importing the same export repeatedly won't duplicate episodes.
        Embeddings are recomputed from the (possibly edited) text rather than
        trusting stale vectors, since export_to_json never included them.
        """
        in_path = Path(path).expanduser()
        count = self.import_from_json_text(in_path.read_text(encoding="utf-8"), recompute_embeddings)
        log.info("Gedächtnis aus %s importiert (%d Einträge verarbeitet)", in_path, count)
        return count

    def import_from_json_text(self, json_text: str, recompute_embeddings: bool = True) -> int:
        """Same as import_from_json(), but takes the JSON content directly
        rather than a file path - used by the gRPC "Importieren" flow
        (Block 6, Phase 54), where the WinUI file picker already has the
        file's bytes in memory and a round-trip through a temp file on disk
        would be pure overhead."""
        data = json.loads(json_text)

        provider = None
        if recompute_embeddings:
            from tarno_backend.memory.embeddings import get_default_provider
            provider = get_default_provider()

        count = 0
        for fact in data.get("facts", []):
            embedding = provider.embed_one(f"{fact['key']}: {fact['value']}") if provider else None
            self.save_fact(fact["key"], fact["value"], fact.get("source", "manual"), embedding=embedding)
            count += 1

        for pref in data.get("preferences", []):
            self.set_preference(pref["key"], pref["value"], pref.get("confidence", 0.5))
            count += 1

        existing_episode_keys = {
            (row["summary"], row["created_at"])
            for row in self._get_conn().execute("SELECT summary, created_at FROM episodes")
        }
        for episode in data.get("episodes", []):
            key = (episode["summary"], episode["created_at"])
            if key in existing_episode_keys:
                continue
            embedding = provider.embed_one(episode["summary"]) if provider else None
            self.save_episode(episode["summary"], episode.get("tags", []), embedding=embedding)
            count += 1

        return count

    def delete_all(self) -> None:
        with self._lock:
            with self._get_conn():
                self._get_conn().execute("DELETE FROM facts")
                self._get_conn().execute("DELETE FROM episodes")
                self._get_conn().execute("DELETE FROM preferences")
