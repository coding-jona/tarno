"""Real browser automation via Playwright - lets TARNO actually interact with
a website (type into fields, click buttons) instead of only reading it
(fetch_webpage) or handing it to the user (open_browser).

Uses Playwright's DOM-based locators (find an element by its visible text,
label, or placeholder) rather than pixel-coordinate clicking - much more
reliable for "fill in this form" than a screenshot-based computer-use
approach would be, and doesn't need a vision model in the loop at all.
"""

from __future__ import annotations

import logging
import threading

from tarno.core.action_result import ActionResult

log = logging.getLogger(__name__)

_READ_MAX_CHARS = 6000
_ACTION_TIMEOUT_MS = 8000


class _BrowserSession:
    """Lazily-started, reused Playwright browser + single page.

    All Playwright calls must happen on the same thread that started it
    (sync API requirement) - the tool-call executor already runs every tool
    handler on one single worker thread (ThreadPoolExecutor(max_workers=1)
    in tarno/grpc/server.py), so this holds naturally without extra thread
    pinning; the lock below just guards against the unlikely case of two
    tool calls overlapping.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._playwright = None
        self._browser = None
        self._page = None

    def _ensure_started(self):
        if self._page is not None:
            return self._page
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        return self._page

    def navigate(self, url: str) -> ActionResult:
        with self._lock:
            try:
                page = self._ensure_started()
                page.goto(url, timeout=_ACTION_TIMEOUT_MS * 2, wait_until="domcontentloaded")
                title = page.title()
                text = _visible_text(page)
                return ActionResult(
                    success=True,
                    message=f"Seite geöffnet: {title}\n\n{text[:_READ_MAX_CHARS]}",
                )
            except Exception as exc:
                log.exception("Browser-Navigation fehlgeschlagen: %s", url)
                return ActionResult.from_exception(exc, message=f"Navigation fehlgeschlagen: {exc}")

    def read(self) -> ActionResult:
        with self._lock:
            if self._page is None:
                return ActionResult(success=False, message="Kein Browser-Fenster offen - zuerst browser_navigate nutzen.")
            try:
                text = _visible_text(self._page)
                truncated = len(text) > _READ_MAX_CHARS
                message = text[:_READ_MAX_CHARS]
                if truncated:
                    message += "\n\n[... gekürzt, Seite ist länger ...]"
                return ActionResult(success=True, message=message)
            except Exception as exc:
                log.exception("Seite lesen fehlgeschlagen")
                return ActionResult.from_exception(exc, message=f"Lesen fehlgeschlagen: {exc}")

    def type_into(self, target: str, value: str) -> ActionResult:
        with self._lock:
            if self._page is None:
                return ActionResult(success=False, message="Kein Browser-Fenster offen - zuerst browser_navigate nutzen.")
            try:
                locator = _find_input(self._page, target)
                if locator is None:
                    return ActionResult(success=False, message=f"Kein Eingabefeld gefunden für: '{target}'")
                locator.fill(value, timeout=_ACTION_TIMEOUT_MS)
                return ActionResult(success=True, message=f"'{value}' in Feld '{target}' eingegeben.")
            except Exception as exc:
                log.exception("Eingabe fehlgeschlagen: %s", target)
                return ActionResult.from_exception(exc, message=f"Eingabe fehlgeschlagen: {exc}")

    def click(self, target: str) -> ActionResult:
        with self._lock:
            if self._page is None:
                return ActionResult(success=False, message="Kein Browser-Fenster offen - zuerst browser_navigate nutzen.")
            try:
                locator = _find_clickable(self._page, target)
                if locator is None:
                    return ActionResult(success=False, message=f"Kein klickbares Element gefunden für: '{target}'")
                locator.click(timeout=_ACTION_TIMEOUT_MS)
                self._page.wait_for_load_state("domcontentloaded", timeout=_ACTION_TIMEOUT_MS)
                text = _visible_text(self._page)
                return ActionResult(success=True, message=f"'{target}' geklickt.\n\n{text[:_READ_MAX_CHARS]}")
            except Exception as exc:
                log.exception("Klick fehlgeschlagen: %s", target)
                return ActionResult.from_exception(exc, message=f"Klick fehlgeschlagen: {exc}")

    def close(self) -> ActionResult:
        with self._lock:
            try:
                if self._browser is not None:
                    self._browser.close()
                if self._playwright is not None:
                    self._playwright.stop()
            except Exception:
                log.exception("Fehler beim Schließen des automatisierten Browsers")
            finally:
                self._browser = None
                self._page = None
                self._playwright = None
            return ActionResult(success=True, message="Automatisierter Browser geschlossen.")


def _visible_text(page) -> str:
    text = page.locator("body").inner_text(timeout=_ACTION_TIMEOUT_MS)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _find_input(page, target: str):
    """Try common ways a human would identify a field: visible label,
    placeholder text, or a raw CSS selector as a last resort. Found live:
    some real forms (e.g. DuckDuckGo's own search box) have no accessible
    label/placeholder/role name at all - if exactly one text input exists on
    the whole page, that's an unambiguous last-resort match."""
    for attempt in (
        lambda: page.get_by_label(target, exact=False),
        lambda: page.get_by_placeholder(target, exact=False),
        lambda: page.get_by_role("textbox", name=target, exact=False),
        lambda: page.locator(target),
    ):
        try:
            locator = attempt()
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue
    try:
        only_input = page.locator("input[type=text], input[type=search], input:not([type]), textarea")
        if only_input.count() == 1:
            return only_input.first
    except Exception:
        pass
    return None


def _find_clickable(page, target: str):
    """Try common ways a human would identify a button/link: visible text,
    accessible role+name, or a raw CSS selector as a last resort. Same
    single-match fallback as _find_input for unlabeled submit buttons."""
    for attempt in (
        lambda: page.get_by_role("button", name=target, exact=False),
        lambda: page.get_by_role("link", name=target, exact=False),
        lambda: page.get_by_text(target, exact=False),
        lambda: page.locator(target),
    ):
        try:
            locator = attempt()
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue
    try:
        only_submit = page.locator("button, input[type=submit]")
        if only_submit.count() == 1:
            return only_submit.first
    except Exception:
        pass
    return None


_session = _BrowserSession()


def browser_navigate(url: str) -> ActionResult:
    if not url.startswith(("http://", "https://")):
        return ActionResult(success=False, message="Ungültige URL (nur http/https erlaubt).")
    return _session.navigate(url)


def browser_read() -> ActionResult:
    return _session.read()


def browser_type(target: str, value: str) -> ActionResult:
    return _session.type_into(target, value)


def browser_click(target: str) -> ActionResult:
    return _session.click(target)


def browser_close() -> ActionResult:
    return _session.close()
