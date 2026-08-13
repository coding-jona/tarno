# `tarno_backend/integrations/` — built-in plugins

Each subfolder is one integration, loaded as a plugin via `tarno_backend/plugins/`
(see `plugin.py` + `plugin.yaml` in each). Every integration follows the
same shape: `client.py` (the actual API/protocol wrapper) + `plugin.py`
(the TARNO-facing plugin adapter) + `plugin.yaml` (manifest).

- **`calendar_email/`**: reads calendar/email for proactive briefings
  (feeds `tarno_backend/core/proactive_briefing.py`).
- **`discord/`**: controls the local Discord client's microphone
  (push-to-talk); the PTT feature needs the optional `pynput` dependency
  (see root `requirements.txt` comments) and degrades gracefully without it.
- **`git/`**: local git developer-tool helpers.
- **`minecraft/`**: talks to the Minecraft "Simple Voice Chat" companion mod.
- **`smart_home/`**: vendor-agnostic smart-home device abstraction.
- **`mesh/`**: by far the largest integration — "Dynamic Hybrid Mesh",
  TARNO running across multiple devices (this PC, a second phone, an
  ESP32-S3 scanner). Has its own embedded MQTT broker (`broker.py`),
  UDP telemetry listener (`udp_listener.py`), presence/heartbeat tracking
  (`heartbeat.py`), a 4-scenario hub-failover state machine (`router.py`),
  a read-only client for the separate `tarno-server` FastAPI backend
  (`cloud_client.py`), and a deliberately un-friendly persona reserved for
  autonomous mesh-triggered actions (`persona.py`).

## Cross-references

- Plugin loading mechanism: `tarno_backend/plugins/manager.py`
- Mesh has its own currently-parked follow-on branch, `feature/dynamic-hybrid-mesh` — check before starting new mesh work in case it overlaps.
- Test coverage: [`workspace/debug/docs/test-coverage-report.md`](../../../workspace/debug/docs/test-coverage-report.md) rates most of these "Basis" (13 tests total across all integrations) — thin coverage, be careful with refactors here.
