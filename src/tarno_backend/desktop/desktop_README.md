# `tarno_backend/desktop/` — Windows desktop control tools

LLM-callable tools for controlling the local desktop: launching apps, managing
windows, taking screenshots, reading system info, and file operations. All of
these are potentially destructive/system-modifying actions and go through the
same permission-confirmation round-trip as any other tool call (see
`grpc/server.py`'s `PermissionDialog` handling).

## Files

- **`app_control.py`**: launch and close desktop applications.
- **`file_manager.py`**: file system operations — open, search, copy, move,
  delete.
- **`screenshot.py`**: screenshot capture.
- **`system_info.py`**: system information retrieval (OS, hardware, running
  processes).
- **`window_manager.py`**: window/process enumeration and control via the
  Win32 API (`pywin32`). Windows-only — no cross-platform fallback.

## Cross-references

- Tool registration: `tarno_backend/ai/tool_registry.py` (see `ai_README.md`)
- Permission round-trip for destructive actions: `tarno_backend/grpc/server.py`
  (see `grpc_README.md`, TD-025)
- Audit trail for what these tools actually did: `tarno_backend/security/audit.py`
  (see `security_README.md`)
