"""Tests for TARNO memory store, retrieval and privacy controls."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

from tarno_backend.memory.preferences import PreferenceManager
from tarno_backend.memory.privacy import MemoryPrivacy
from tarno_backend.memory.retrieval import MemoryRetriever
from tarno_backend.memory.store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    """Tests for MemoryStore."""

    def setUp(self) -> None:
        self.store = MemoryStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_save_and_get_fact(self):
        self.store.save_fact("lieblingsfarbe", "blau", source="user")
        fact = self.store.get_fact("lieblingsfarbe")
        self.assertIsNotNone(fact)
        self.assertEqual(fact.value, "blau")

    def test_update_fact(self):
        self.store.save_fact("farbe", "rot")
        self.store.save_fact("farbe", "grün")
        fact = self.store.get_fact("farbe")
        self.assertEqual(fact.value, "grün")

    def test_search_facts(self):
        self.store.save_fact("musik", "Rock", "user")
        self.store.save_fact("app", "Firefox", "user")
        results = self.store.search_facts("Rock")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, "musik")

    def test_episodes(self):
        self.store.save_episode("Besprechung über Projekt X", tags=["arbeit"])
        episodes = self.store.get_recent_episodes()
        self.assertEqual(len(episodes), 1)
        self.assertIn("arbeit", episodes[0].tags)

    def test_preferences(self):
        self.store.set_preference("sprache", "deutsch", 0.9)
        pref = self.store.get_preference("sprache")
        self.assertEqual(pref["value"], "deutsch")


class MemoryRetrieverTests(unittest.TestCase):
    """Tests for MemoryRetriever."""

    def setUp(self) -> None:
        self.store = MemoryStore(":memory:")
        self.retriever = MemoryRetriever(self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_retrieve_relevant_facts(self):
        self.store.save_fact("farbe", "blau")
        self.store.save_fact("stadt", "Berlin")
        results = self.retriever.retrieve("farbe", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].kind, "fact")


class PreferenceManagerTests(unittest.TestCase):
    """Tests for PreferenceManager."""

    def setUp(self) -> None:
        self.store = MemoryStore(":memory:")
        self.manager = PreferenceManager(self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_record_explicit(self):
        self.manager.record_explicit("musik", "Jazz")
        pref = self.manager.get("musik")
        self.assertEqual(pref["value"], "Jazz")

    def test_infer_positive_preference(self):
        candidates = self.manager.infer_from_utterance("Ich höre gerne Rock")
        self.assertTrue(any(c["key"] == "music_preference" for c in candidates))


class MemoryPrivacyTests(unittest.TestCase):
    """Tests for MemoryPrivacy."""

    def setUp(self) -> None:
        self.store = MemoryStore(":memory:")
        self.privacy = MemoryPrivacy(self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_delete_facts_by_key(self):
        self.store.save_fact("x", "y")
        self.privacy.delete_facts_by_key("x")
        self.assertIsNone(self.store.get_fact("x"))


class MemoryStoreThreadTests(unittest.TestCase):
    """Regression tests for SQLite thread safety."""

    def test_access_from_different_thread(self):
        store = MemoryStore(":memory:")
        store.save_fact("thread_test", "value", source="user")
        captured: list[Any] = []

        def worker() -> None:
            try:
                fact = store.get_fact("thread_test")
                captured.append(fact.value if fact else None)
            except Exception as e:
                captured.append(e)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        store.close()
        self.assertEqual(captured, ["value"])

    def test_search_from_different_thread(self):
        store = MemoryStore(":memory:")
        store.save_fact("thread_search", "find me", source="user")
        captured: list[Any] = []

        def worker() -> None:
            try:
                results = store.search_facts("find")
                captured.append([r.key for r in results])
            except Exception as e:
                captured.append(e)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        store.close()
        self.assertEqual(captured, [["thread_search"]])


if __name__ == "__main__":
    unittest.main()
