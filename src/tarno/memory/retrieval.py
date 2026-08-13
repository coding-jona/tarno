"""Memory retrieval helpers combining keyword search, semantic similarity and recency."""

from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tarno.memory.store import MemoryStore

if TYPE_CHECKING:
    import numpy as np


@dataclass
class RankedMemory:
    kind: str  # 'fact', 'episode', 'preference'
    content: str
    score: float


class MemoryRetriever:
    """Ranks memory entries for injection into the LLM context.

    Combines three signals (Block 4, Phase 31/33):
    - Keyword/substring matching (original behavior, always available).
    - Semantic similarity via local ONNX embeddings, when the embedding model
      is available - falls back gracefully to keyword-only if not (e.g. model
      not yet downloaded, see tarno/memory/embeddings.py).
    - A small recency boost so newer memories edge out equally-relevant older ones.
    """

    def __init__(self, store: MemoryStore, embedding_weight: float = 0.6) -> None:
        self._store = store
        self._embedding_weight = embedding_weight

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        recency_days: int | None = 30,
    ) -> list[RankedMemory]:
        """Return the most relevant memory entries for a query."""
        cutoff = datetime.now() - timedelta(days=recency_days) if recency_days else None
        candidates: dict[tuple[str, int | None], tuple[RankedMemory, datetime]] = {}

        for fact in self._store.search_facts(query, limit=limit * 2):
            candidates[("fact", fact.id)] = (
                RankedMemory(
                    kind="fact",
                    content=f"{fact.key}: {fact.value}",
                    score=self._score(fact.key, fact.value, query),
                ),
                fact.updated_at,
            )

        for episode in self._store.get_recent_episodes(limit=limit * 2):
            if cutoff and episode.created_at < cutoff:
                continue
            candidates[("episode", episode.id)] = (
                RankedMemory(
                    kind="episode",
                    content=episode.summary,
                    score=self._score(episode.summary, ", ".join(episode.tags), query),
                ),
                episode.created_at,
            )

        query_vector = self._embed_query(query)
        if query_vector is not None:
            self._merge_semantic_facts(candidates, query_vector, limit)
            self._merge_semantic_episodes(candidates, query_vector, limit, cutoff)

        # Combine relevance and recency (newer items get a small boost).
        now = datetime.now()
        scored = []
        for memory, timestamp in candidates.values():
            age_days = (now - timestamp).total_seconds() / 86400.0
            recency_boost = max(0.0, 1.0 - age_days / 30.0) * 0.2
            scored.append(RankedMemory(
                kind=memory.kind,
                content=memory.content,
                score=memory.score + recency_boost,
            ))

        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:limit]

    def _merge_semantic_facts(
        self,
        candidates: dict[tuple[str, int | None], tuple[RankedMemory, datetime]],
        query_vector: "np.ndarray",
        limit: int,
    ) -> None:
        for fact, similarity in self._store.search_facts_by_vector(query_vector, limit=limit * 2):
            key = ("fact", fact.id)
            # Scaled into roughly the same range as the keyword scorer's
            # (unbounded but typically 0-2) output, weighted by embedding_weight.
            semantic_score = similarity * self._embedding_weight * 2
            content = f"{fact.key}: {fact.value}"
            if key in candidates:
                existing, ts = candidates[key]
                candidates[key] = (
                    RankedMemory(kind="fact", content=content, score=max(existing.score, semantic_score)),
                    ts,
                )
            else:
                candidates[key] = (
                    RankedMemory(kind="fact", content=content, score=semantic_score),
                    fact.updated_at,
                )

    def _merge_semantic_episodes(
        self,
        candidates: dict[tuple[str, int | None], tuple[RankedMemory, datetime]],
        query_vector: "np.ndarray",
        limit: int,
        cutoff: datetime | None,
    ) -> None:
        for episode, similarity in self._store.search_episodes_by_vector(query_vector, limit=limit * 2):
            if cutoff and episode.created_at < cutoff:
                continue
            key = ("episode", episode.id)
            semantic_score = similarity * self._embedding_weight * 2
            if key in candidates:
                existing, ts = candidates[key]
                candidates[key] = (
                    RankedMemory(kind="episode", content=episode.summary, score=max(existing.score, semantic_score)),
                    ts,
                )
            else:
                candidates[key] = (
                    RankedMemory(kind="episode", content=episode.summary, score=semantic_score),
                    episode.created_at,
                )

    @staticmethod
    def _embed_query(query: str) -> "np.ndarray | None":
        from tarno.memory.embeddings import get_default_provider
        return get_default_provider().embed_one(query)

    @staticmethod
    def _score(key: str, value: str, query: str) -> float:
        query_lower = query.lower()
        key_score = 1.0 if query_lower in key.lower() else 0.0
        value_tokens = value.lower().split()
        query_tokens = query_lower.split()
        if not value_tokens:
            return key_score
        matches = sum(1 for t in query_tokens if t in value_tokens)
        return key_score + matches / len(value_tokens)
