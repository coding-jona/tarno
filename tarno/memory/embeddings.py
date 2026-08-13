"""Local ONNX text embeddings for semantic memory search (Block 4, Phasen 31/38).

Uses fastembed (pure onnxruntime, no PyTorch/heavy ML framework) with a small
multilingual model - onnxruntime is already a project dependency (openWakeWord),
so this avoids introducing a second, heavier ML stack (e.g. sentence-transformers
+ PyTorch, or a full vector-DB server like ChromaDB/Qdrant) purely to get
semantic similarity. Vectors are stored as BLOBs in the existing MemoryStore
SQLite database (see memory/store.py) rather than a separate vector store.
"""

from __future__ import annotations

import logging
import struct
from typing import Sequence

import numpy as np

log = logging.getLogger(__name__)

# Multilingual (~50 languages incl. German), 384-dim, ~0.22 GB ONNX - the
# smallest fastembed-supported model with real German support. Downloaded
# once to the fastembed/huggingface cache on first use, then fully offline.
_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


class EmbeddingProvider:
    """Lazily loads the ONNX embedding model and encodes text to float32 vectors."""

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None  # lazy: avoid the ~1-2s model load if memory/search is unused

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        try:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self._model_name)
            log.info("Embedding-Modell geladen: %s", self._model_name)
            return True
        except Exception:
            log.exception(
                "Embedding-Modell konnte nicht geladen werden - "
                "Gedächtnissuche fällt auf Keyword-Matching zurück"
            )
            return False

    @property
    def available(self) -> bool:
        return self._ensure_loaded()

    def embed(self, texts: Sequence[str]) -> list[np.ndarray] | None:
        """Encode texts to float32 unit vectors. Returns None if the model
        isn't available (caller should fall back to keyword-only search)."""
        if not texts:
            return []
        if not self._ensure_loaded():
            return None
        try:
            vectors = list(self._model.embed(list(texts)))
            return [np.asarray(v, dtype=np.float32) for v in vectors]
        except Exception:
            log.exception("Embedding-Erzeugung fehlgeschlagen")
            return None

    def embed_one(self, text: str) -> np.ndarray | None:
        vectors = self.embed([text])
        if not vectors:
            return None
        return vectors[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors, 0.0 if either is a zero vector."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def vector_to_blob(vector: np.ndarray) -> bytes:
    """Serialize a float32 vector to bytes for SQLite BLOB storage."""
    return struct.pack(f"<{len(vector)}f", *vector.astype(np.float32).tolist())


def blob_to_vector(blob: bytes) -> np.ndarray:
    """Deserialize a BLOB back to a float32 numpy vector."""
    count = len(blob) // 4
    return np.array(struct.unpack(f"<{count}f", blob), dtype=np.float32)


# Process-wide singleton - the model is ~stateless and thread-safe for
# inference, so sharing one instance avoids reloading it per MemoryStore.
_default_provider: EmbeddingProvider | None = None


def get_default_provider() -> EmbeddingProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = EmbeddingProvider()
    return _default_provider
