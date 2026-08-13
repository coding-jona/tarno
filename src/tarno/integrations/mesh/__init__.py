"""TARNO Dynamic Hybrid Mesh integration.

Aggregates telemetry from the mesh nodes (secondary phone, ESP32-S3 proximity
scanner, hub phone acting as primary hub) and reacts via TARNO's existing
proactive-commentary/TTS path. See ``plugin.py`` for the entrypoint and
``router.py`` for the 4-scenario hub failover state machine.

Disabled by default (``mesh.enabled = False`` in TarnoConfig) - adding this
package changes nothing for existing users until explicitly opted in.
"""
