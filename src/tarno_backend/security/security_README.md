# `tarno_backend/security/` — secrets, encryption, PII, audit, build safety

Security-relevant helpers used across the whole backend. Small, focused
modules rather than one monolithic "security" god-module, so each concern
(secrets vs. encryption vs. PII vs. audit) can be reasoned about and tested
independently.

## Files

- **`secrets.py`**: `SecretsVault` abstraction for API keys and tokens
  (OS keyring-backed by default, `encrypted_file` fallback). Uses the
  literal service identifier `"tarno"` in the OS keyring — **deliberately
  not renamed** to `tarno_backend` during the package rename, since that
  would orphan every API key already stored under the old name on real
  installs. Write-locking for the `encrypted_file` backend is a known gap,
  see TD-019.
- **`encryption.py`**: encryption-at-rest helpers (`DataEncryption`) for
  sensitive data and files.
- **`pii.py`**: PII redaction (`redact`, `redact_dict`) for logs and LLM
  context — emails, phone numbers, etc.
- **`audit.py`**: `AuditManager` — audit-log integrity verification (tamper
  detection via hash chaining) and retention/rotation.
- **`content_filter.py`**: Zero-Trust content filter for the LLM pipeline —
  treats tool output and web content as untrusted input before it re-enters
  a prompt.
- **`build_secret_scan.py`**: build-time scan (`verify_no_secrets`) that
  fails a build if a real-looking secret pattern is found in files about to
  be shipped; allows documented placeholders like `<your_key_here>`.

## Cross-references

- Keyring/service-name rationale and other product-surface strings that must
  never be renamed: see the "package rename" note in
  [`utils/paths.py`](../utils/utils_README.md) and the rename commit.
- Known gap: TD-019 (SecretsVault `encrypted_file` write-locking) in
  [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md)
- PII redaction wired into logging: `tarno_backend/telemetry/logging.py`
  (see `telemetry_README.md`)
- Exercised together in [`workspace/debug/tests/test_security.py`](../../../workspace/debug/tests/test_security.py)
