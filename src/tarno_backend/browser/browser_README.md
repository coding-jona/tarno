# `tarno_backend/browser/` — web/browser control tools

Lets TARNO act on the open web: driving a real browser via Playwright and
exposing simpler read/navigate actions as LLM tool calls.

## Files

- **`browser_automation.py`**: real browser automation via Playwright — launches/
  attaches to a browser, navigates, clicks, fills forms, reads page content.
  This is the tool the LLM reaches for when a task needs actual interaction
  with a website (not just fetching a URL's content).
- **`web_control.py`**: lighter-weight browser and web control — the tool-schema
  wrapper exposed to `tarno_backend/ai/tool_registry.py`, delegating to
  `browser_automation.py` for the actual Playwright driving.

## Cross-references

- Tool registration: `tarno_backend/ai/tool_registry.py` (see `ai_README.md`)
- Content safety for anything read back from a page: `tarno_backend/security/content_filter.py`
  (see `security_README.md`) — untrusted web content is treated the same as
  untrusted LLM output before being fed back into a prompt.
