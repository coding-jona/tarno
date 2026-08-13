"""Tests for the Dynamic Hybrid Mesh plugin (payload parsing, router scenario
transitions, observer draft/cooldown behaviour). All pure in-process - no
real sockets, no amqtt/paho-mqtt required (broker.start()/mqtt_bridge.connect()
already degrade gracefully to a logged no-op when those optional deps are
missing, so the router logic is fully testable without them installed)."""

from __future__ import annotations

import time
import unittest

from tarno_backend.core.events import EventBus, MeshScenarioChangedEvent
from tarno_backend.integrations.mesh.broker import EmbeddedMqttBroker
from tarno_backend.integrations.mesh.heartbeat import ESP32, HUB, SECONDARY, HeartbeatMonitor
from tarno_backend.integrations.mesh.mqtt_bridge import MqttBridge
from tarno_backend.integrations.mesh.observer import MeshObserver
from tarno_backend.integrations.mesh.payload import MeshEvent
from tarno_backend.integrations.mesh.router import FULL_MESH, PC_FALLBACK, SOLO_PC, MeshRouter


class PayloadTests(unittest.TestCase):
    def test_round_trip(self):
        event = MeshEvent(
            sender_node="ZTE_BLADE_V70",
            target_hub="DYNAMIC_BROADCAST",
            timestamp=1718000000.0,
            event_type="USER_STATE_CHANGE",
            payload={"screen_state": "ON", "battery_level": 78},
        )
        parsed = MeshEvent.from_json(event.to_json())
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.sender_node, "ZTE_BLADE_V70")
        self.assertEqual(parsed.payload["battery_level"], 78)

    def test_malformed_json_returns_none(self):
        self.assertIsNone(MeshEvent.from_json(b"not json"))
        self.assertIsNone(MeshEvent.from_json("{}"))  # missing required fields
        self.assertIsNone(MeshEvent.from_json('{"sender_node": "X"}'))  # missing event_type
        self.assertIsNone(MeshEvent.from_json("[1, 2, 3]"))  # not an object

    def test_defaults_applied_for_optional_fields(self):
        parsed = MeshEvent.from_json('{"sender_node": "ESP32_S3_SCANNER", "event_type": "PROXIMITY_UPDATE"}')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.target_hub, "DYNAMIC_BROADCAST")
        self.assertEqual(parsed.payload, {})
        self.assertGreater(parsed.timestamp, 0.0)


class RouterScenarioTests(unittest.TestCase):
    def _make_router(self) -> tuple[MeshRouter, HeartbeatMonitor, list]:
        heartbeat = HeartbeatMonitor(heartbeat_interval_seconds=0.01)
        broker = EmbeddedMqttBroker(port=18830)  # arbitrary test-only port, never actually bound
        bridge = MqttBridge()
        transitions: list = []
        router = MeshRouter(
            heartbeat=heartbeat,
            embedded_broker=broker,
            hub_bridge=bridge,
            on_transition=transitions.append,
        )
        return router, heartbeat, transitions

    def test_solo_pc_when_nothing_online(self):
        router, _heartbeat, transitions = self._make_router()
        router.tick()
        # Initial scenario is already SOLO_PC (conservative default), so a
        # tick with nothing online must NOT fire a transition.
        self.assertEqual(router.scenario, SOLO_PC)
        self.assertEqual(len(transitions), 0)

    def test_full_mesh_when_wiko_online(self):
        router, heartbeat, transitions = self._make_router()
        heartbeat.mark_seen(HUB)
        router.tick()
        self.assertEqual(router.scenario, FULL_MESH)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0].current, FULL_MESH)
        self.assertEqual(transitions[0].previous, SOLO_PC)

    def test_pc_fallback_when_wiko_offline_but_zte_online(self):
        router, heartbeat, transitions = self._make_router()
        heartbeat.mark_seen(SECONDARY)
        router.tick()
        self.assertEqual(router.scenario, PC_FALLBACK)
        self.assertEqual(transitions[-1].current, PC_FALLBACK)

    def test_full_mesh_takes_priority_over_zte(self):
        router, heartbeat, _transitions = self._make_router()
        heartbeat.mark_seen(HUB)
        heartbeat.mark_seen(SECONDARY)
        router.tick()
        self.assertEqual(router.scenario, FULL_MESH)

    def test_esp32_alone_does_not_trigger_pc_fallback(self):
        # Per spec: PC_FALLBACK requires a phone (SECONDARY); ESP32-only stays SOLO_PC.
        router, heartbeat, transitions = self._make_router()
        heartbeat.mark_seen(ESP32)
        router.tick()
        self.assertEqual(router.scenario, SOLO_PC)
        self.assertEqual(len(transitions), 0)

    def test_no_duplicate_transition_on_repeated_tick(self):
        router, heartbeat, transitions = self._make_router()
        heartbeat.mark_seen(HUB)
        router.tick()
        router.tick()
        router.tick()
        self.assertEqual(len(transitions), 1)  # only the one real change

    def test_record_event_marks_correct_node(self):
        router, heartbeat, _transitions = self._make_router()
        router.record_event(MeshEvent(sender_node="ZTE_BLADE_V70", event_type="X"))
        self.assertTrue(heartbeat.is_online(SECONDARY))
        self.assertFalse(heartbeat.is_online(HUB))


class HeartbeatMonitorTests(unittest.TestCase):
    def test_times_out_after_3x_interval(self):
        monitor = HeartbeatMonitor(heartbeat_interval_seconds=0.02)
        monitor.mark_seen(HUB)
        self.assertTrue(monitor.is_online(HUB))
        time.sleep(0.08)  # > 3x 0.02s timeout
        self.assertFalse(monitor.is_online(HUB))

    def test_unknown_node_is_offline(self):
        monitor = HeartbeatMonitor()
        self.assertFalse(monitor.is_online("NEVER_SEEN"))


class MeshObserverTests(unittest.TestCase):
    def test_no_draft_without_transition(self):
        bus = EventBus()
        observer = MeshObserver(bus)
        self.assertIsNone(observer.check())

    def test_draft_on_scenario_change(self):
        bus = EventBus()
        observer = MeshObserver(bus)
        bus.publish(MeshScenarioChangedEvent(scenario=PC_FALLBACK, previous=FULL_MESH))
        draft = observer.check()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.source, "mesh")
        # persona.py's comment() picks randomly between multiple phrasings
        # per event type (see its module docstring) - "Hub-Rolle" only
        # appears in the HUB_FULL_MESH variants, not HUB_FALLBACK_PC (the
        # scenario actually triggered here). Assert against both possible
        # HUB_FALLBACK_PC phrasings instead of one specific, wrong string.
        self.assertTrue(
            "Hub-Handy nicht erreichbar" in draft.message
            or "Hub-Node offline" in draft.message,
            f"unexpected mesh fallback message: {draft.message!r}",
        )

    def test_draft_consumed_only_once(self):
        bus = EventBus()
        observer = MeshObserver(bus)
        bus.publish(MeshScenarioChangedEvent(scenario=FULL_MESH, previous=SOLO_PC))
        first = observer.check()
        second = observer.check()
        self.assertIsNotNone(first)
        self.assertIsNone(second)  # buffer drained, no repeat draft


if __name__ == "__main__":
    unittest.main()
