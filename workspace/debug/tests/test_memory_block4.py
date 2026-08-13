"""Tests for Block 4 (Kontextuelles Gedächtnis & Memory-Layer, Phasen 31-40).

Embedding-model-dependent tests (real semantic similarity) are kept few and
targeted to avoid slow test runs; most store/pruning/extraction/persona-guard
tests use synthetic vectors or run without embeddings entirely.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from tarno_backend.ai.persona_guard import PersonaGuard
from tarno_backend.memory.embeddings import blob_to_vector, cosine_similarity, vector_to_blob
from tarno_backend.memory.fact_extractor import FactExtractor
from tarno_backend.memory.store import MemoryStore


class VectorBlobTests(unittest.TestCase):
    def test_roundtrip_preserves_values(self) -> None:
        vec = np.array([0.1, -0.5, 0.999, -1.0, 0.0], dtype=np.float32)
        restored = blob_to_vector(vector_to_blob(vec))
        np.testing.assert_array_almost_equal(vec, restored, decimal=6)

    def test_cosine_similarity_identical_vectors(self) -> None:
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(vec, vec), 1.0, places=5)

    def test_cosine_similarity_orthogonal_vectors(self) -> None:
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0, places=5)

    def test_cosine_similarity_zero_vector_is_safe(self) -> None:
        a = np.array([0.0, 0.0], dtype=np.float32)
        b = np.array([1.0, 1.0], dtype=np.float32)
        self.assertEqual(cosine_similarity(a, b), 0.0)


class MemoryStoreVectorSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        # MemoryStore(":memory:") uses a named SQLite shared-cache, so every
        # instance in this process sees the SAME tables (intentional, for
        # multi-threaded use of one instance) - reset explicitly so each test
        # method here starts from a clean slate instead of leaking data
        # between test methods and test classes.
        self.store = MemoryStore(":memory:")
        self.store.delete_all()

    def test_search_facts_by_vector_ranks_by_similarity(self) -> None:
        close = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        far = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.store.save_fact("a", "close match", embedding=close)
        self.store.save_fact("b", "far match", embedding=far)

        results = self.store.search_facts_by_vector(close, limit=5, min_similarity=0.0)
        self.assertEqual(results[0][0].key, "a")
        self.assertGreater(results[0][1], results[1][1])

    def test_facts_without_embedding_excluded_from_vector_search(self) -> None:
        self.store.save_fact("no_embedding", "value")  # no embedding param
        query = np.array([1.0, 0.0], dtype=np.float32)
        self.assertEqual(self.store.search_facts_by_vector(query, min_similarity=0.0), [])

    def test_min_similarity_filters_low_matches(self) -> None:
        orthogonal = np.array([0.0, 1.0], dtype=np.float32)
        self.store.save_fact("x", "y", embedding=orthogonal)
        query = np.array([1.0, 0.0], dtype=np.float32)
        self.assertEqual(self.store.search_facts_by_vector(query, min_similarity=0.5), [])

    def test_search_episodes_by_vector(self) -> None:
        vec = np.array([1.0, 0.0], dtype=np.float32)
        self.store.save_episode("Ein Ereignis", tags=["test"], embedding=vec)
        results = self.store.search_episodes_by_vector(vec, min_similarity=0.0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].summary, "Ein Ereignis")

    def test_updating_fact_without_embedding_preserves_existing_one(self) -> None:
        """Regression guard: remember_fact()-style updates that don't pass a
        fresh embedding must not silently null out a previously computed one."""
        vec = np.array([1.0, 0.0], dtype=np.float32)
        self.store.save_fact("k", "v1", embedding=vec)
        self.store.save_fact("k", "v2")  # no embedding this time
        results = self.store.search_facts_by_vector(vec, min_similarity=0.0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].value, "v2")  # value updated
        # embedding survived the update (still findable by the original vector)
        self.assertGreater(results[0][1], 0.9)


class MemoryPruningTests(unittest.TestCase):
    def setUp(self) -> None:
        # See MemoryStoreVectorSearchTests.setUp() - ":memory:" shares a
        # process-wide SQLite cache, so reset explicitly per test method.
        self.store = MemoryStore(":memory:")
        self.store.delete_all()

    def test_prunes_old_episodes(self) -> None:
        self.store.save_episode("Alt", tags=[])
        old_iso = (datetime.now() - timedelta(days=100)).isoformat()
        with self.store._get_conn():  # noqa: SLF001 - directly backdate for the test
            self.store._get_conn().execute(
                "UPDATE episodes SET created_at = ? WHERE summary = 'Alt'", (old_iso,)
            )
        self.store.save_episode("Neu", tags=[])

        result = self.store.prune_stale(episode_max_age_days=30)
        self.assertEqual(result["episodes_deleted"], 1)
        remaining = [e.summary for e in self.store.get_recent_episodes(limit=10)]
        self.assertEqual(remaining, ["Neu"])

    def test_prunes_low_confidence_preferences(self) -> None:
        self.store.set_preference("unsicher", "irgendwas", confidence=0.1)
        self.store.set_preference("sicher", "definitiv", confidence=0.9)

        result = self.store.prune_stale(preference_min_confidence=0.3)
        self.assertEqual(result["preferences_deleted"], 1)
        self.assertIsNone(self.store.get_preference("unsicher"))
        self.assertIsNotNone(self.store.get_preference("sicher"))

    def test_facts_are_never_pruned(self) -> None:
        self.store.save_fact("dauerhaft", "bleibt")
        self.store.prune_stale(episode_max_age_days=0, preference_min_confidence=1.0)
        self.assertIsNotNone(self.store.get_fact("dauerhaft"))


class MemoryInspectorRoundtripTests(unittest.TestCase):
    def test_export_then_import_preserves_facts_and_preferences(self) -> None:
        store = MemoryStore(":memory:")
        store.delete_all()  # see MemoryStoreVectorSearchTests.setUp() - shared cache
        store.save_fact("farbe", "blau", "user")
        store.set_preference("browser", "Firefox", 0.7)
        store.save_episode("Testereignis", tags=["x"])

        with tempfile.TemporaryDirectory() as tmp:
            export_path = Path(tmp) / "export.json"
            count = store.export_to_json(export_path)
            self.assertEqual(count, 3)

            data = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(data["facts"][0]["key"], "farbe")
            self.assertNotIn("embedding", data["facts"][0])  # no raw vectors in export

            # Use a real temp-file DB (not ":memory:") so this store doesn't
            # share the process-wide SQLite shared in-memory cache with `store`.
            fresh_store = MemoryStore(Path(tmp) / "fresh.db")
            try:
                imported = fresh_store.import_from_json(export_path, recompute_embeddings=False)
                self.assertEqual(imported, 3)
                self.assertEqual(fresh_store.get_fact("farbe").value, "blau")
                self.assertEqual(fresh_store.get_preference("browser")["value"], "Firefox")
            finally:
                # Windows won't let TemporaryDirectory clean up while the
                # SQLite file connection is still open.
                fresh_store.close()

    def test_reimporting_same_file_does_not_duplicate_episodes(self) -> None:
        store = MemoryStore(":memory:")
        store.delete_all()  # see MemoryStoreVectorSearchTests.setUp() - shared cache
        store.save_episode("Einmalig", tags=[])

        with tempfile.TemporaryDirectory() as tmp:
            export_path = Path(tmp) / "export.json"
            store.export_to_json(export_path)
            store.import_from_json(export_path, recompute_embeddings=False)
            store.import_from_json(export_path, recompute_embeddings=False)

        episodes = [e.summary for e in store.get_recent_episodes(limit=10)]
        self.assertEqual(episodes.count("Einmalig"), 1)


class FactExtractorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = FactExtractor()

    def test_extracts_name(self) -> None:
        facts = self.extractor.extract("Hallo, ich heiße Jona.")
        self.assertIn(("name", "Jona"), facts)

    def test_extracts_wohnort(self) -> None:
        facts = self.extractor.extract("Ich wohne in Berlin und es gefällt mir.")
        self.assertIn(("wohnort", "Berlin"), facts)

    def test_extracts_lieblingsessen(self) -> None:
        facts = self.extractor.extract("Ich mag Pizza.")
        self.assertIn(("lieblingsessen", "Pizza"), facts)

    def test_name_boundary_not_swallowed_by_following_clause(self) -> None:
        """Regression test (found via live testing): re.IGNORECASE on the
        name/wohnort patterns used to make [A-ZÄÖÜ] match lowercase letters
        too, defeating the capital-letter name boundary and extracting
        "Jona und" instead of "Jona" from a combined sentence."""
        facts = self.extractor.extract("Ich heiße Jona und ich mag Pizza.")
        self.assertIn(("name", "Jona"), facts)
        self.assertIn(("lieblingsessen", "Pizza"), facts)

    def test_extracts_name_lowercase_trigger_variant(self) -> None:
        facts = self.extractor.extract("ich heisse Anna.")
        self.assertIn(("name", "Anna"), facts)

    def test_no_false_positive_on_unrelated_text(self) -> None:
        facts = self.extractor.extract("Wie spät ist es gerade?")
        self.assertEqual(facts, [])


class PersonaGuardTests(unittest.TestCase):
    def test_triggers_exactly_every_n_turns(self) -> None:
        guard = PersonaGuard(reanchor_every_n_turns=3)
        results = [guard.should_reanchor() for _ in range(7)]
        self.assertEqual(results, [False, False, True, False, False, True, False])

    def test_reset_restarts_the_count(self) -> None:
        guard = PersonaGuard(reanchor_every_n_turns=3)
        guard.should_reanchor()
        guard.should_reanchor()
        guard.reset()
        self.assertFalse(guard.should_reanchor())
        self.assertFalse(guard.should_reanchor())
        self.assertTrue(guard.should_reanchor())

    def test_reanchor_text_is_non_empty(self) -> None:
        guard = PersonaGuard()
        self.assertIn("TARNO", guard.reanchor_text)


class EmbeddingSemanticSanityTest(unittest.TestCase):
    """The one real-model test in this file - keeps a fast, targeted check
    that the embedding model actually produces semantically meaningful
    similarity (not just structurally valid vectors)."""

    def test_semantically_similar_sentences_score_higher_than_unrelated(self) -> None:
        from tarno_backend.memory.embeddings import get_default_provider

        provider = get_default_provider()
        if not provider.available:
            self.skipTest("Embedding-Modell nicht verfügbar (nicht heruntergeladen)")

        v1 = provider.embed_one("Ich mag Pizza sehr gerne.")
        v2 = provider.embed_one("Pizza ist mein Lieblingsessen.")
        v3 = provider.embed_one("Das Auto hat eine kaputte Reifen.")

        self.assertGreater(cosine_similarity(v1, v2), cosine_similarity(v1, v3))


if __name__ == "__main__":
    unittest.main()
