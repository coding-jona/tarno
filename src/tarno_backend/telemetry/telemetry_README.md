# `tarno_backend/telemetry/` — structured logging & observability

Centralised logging setup for the whole backend. Everything that calls
`logging.getLogger(...)` relies on the root configuration done here to
actually produce structured, correlated output — see the "Cross-references"
note below on why the logger name prefix matters.

## Files

- **`logging.py`**: `configure_logging()` — sets up structured logging with
  correlation IDs, optional PII redaction (delegates to
  `tarno_backend/security/pii.py`), and log-file output.

## Cross-references

- Facade used by most call sites instead of importing this directly:
  `tarno_backend/utils/log.py` (`setup_logging()`), see `utils_README.md`.
- PII redaction filter: `tarno_backend/security/pii.py` (see `security_README.md`)
- **Logger-hierarchy note:** loggers are attached by name prefix (e.g.
  `logging.getLogger("tarno_backend.grpc")`). During the `tarno` →
  `tarno_backend` package rename, several call sites still used the old
  `"tarno.*"` prefix, which silently broke propagation to any handler
  configured here — always keep logger names in sync with the current
  package name after a rename.
