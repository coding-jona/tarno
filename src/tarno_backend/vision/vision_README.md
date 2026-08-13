# `tarno_backend/vision/` — camera & autonomous vision reactions ("Block 7")

Optional layer giving TARNO a permanent camera feed and the ability to react
autonomously to what it sees, gated behind local motion detection so frames
are only sent to a vision API when something actually changed. Named
"Block 7" in the original phased build plan (see file docstrings, phases
61–68) — kept here for traceability, not a naming convention to imitate
elsewhere.

## Files

- **`camera_capture.py`**: local webcam capture (Phase 61).
- **`motion_gate.py`**: local motion detection (Phase 62) — cheap local gate
  that decides whether a frame is even worth sending to a paid vision API.
- **`preprocessing.py`**: frame preprocessing before any vision-model API
  call (Phase 64) — resize/crop/encode.
- **`vision_provider.py`**: Mistral vision API integration (Phases 65–66) —
  the actual outbound API call.
- **`vision_observer.py`**: the vision observer for the autonomous trigger
  engine (Phases 67–68) — decides when a vision event should trigger an
  autonomous TARNO action/extension.

## Cross-references

- Autonomous actions triggered from vision events: `tarno_backend/extensions/`
  (see `extensions_README.md`)
- Privacy: camera capture is local-only by default; only preprocessed frames
  that pass `motion_gate.py` are sent to `vision_provider.py`'s external API.
