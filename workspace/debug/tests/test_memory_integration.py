"""Tests for Memory integration in the ConversationManager."""

from __future__ import annotations

import unittest

from tarno.ai.conversation import ConversationManager
from tarno.memory.store import MemoryStore


class MemoryIntegrationTests(unittest.TestCase):
    """Tests that ConversationManager can retrieve and inject long-term memory."""

    def test_inject_relevant_memory_adds_context(self):
        store = MemoryStore(":memory:")
        store.save_fact("lieblingsfarbe", "blau")
        conversation = ConversationManager(memory_store=store)
        conversation.add_user_message("Was ist meine Lieblingsfarbe?")
        injected = conversation.inject_relevant_memory("Lieblingsfarbe")
        self.assertTrue(injected)
        messages = conversation.get_messages()
        self.assertTrue(
            any("Langzeitgedächtnis" in str(m.get("content", "")) for m in messages)
        )
        store.close()

    def test_no_injection_when_memory_empty(self):
        store = MemoryStore(":memory:")
        conversation = ConversationManager(memory_store=store)
        conversation.add_user_message("Hallo")
        injected = conversation.inject_relevant_memory("Hallo")
        self.assertFalse(injected)
        store.close()

    def test_remember_fact_persists_in_store(self):
        store = MemoryStore(":memory:")
        conversation = ConversationManager(memory_store=store)
        conversation.remember_fact("stadt", "Berlin")
        fact = store.get_fact("stadt")
        self.assertIsNotNone(fact)
        self.assertEqual(fact.value, "Berlin")
        store.close()


if __name__ == "__main__":
    unittest.main()
