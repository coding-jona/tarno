"""Browser and web control."""

from __future__ import annotations

import html
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from tarno.core.action_result import ActionResult

log = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)
_MAX_RESULTS = 5
_TIMEOUT_SECONDS = 10.0


def _decode_ddg_link(href: str) -> str:
    """DuckDuckGo result links redirect via /l/?uddg=<percent-encoded URL>.

    Found live: this used to base64-decode `uddg`, but DuckDuckGo's `uddg`
    value is a plain percent-encoded URL, not base64 - decoding a real URL
    string as base64 "succeeds" (rarely raises) but produces meaningless
    binary garbage, which was silently making it all the way into the LLM's
    context as a fake "URL", causing fabricated answers instead of an honest
    "couldn't read the results". Falls back to the raw href (still usable,
    just not de-redirected) if the result doesn't look like a real URL."""
    try:
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        uddg = query.get("uddg", [None])[0]
        if not uddg:
            return href
        decoded = urllib.parse.unquote(uddg)
        if decoded.startswith(("http://", "https://")):
            return decoded
        return href
    except Exception:
        return href


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def web_search(query: str) -> ActionResult:
    """Führt eine DuckDuckGo-Suche durch und gibt formatierte Ergebnisse zurück.

    Keine externen Abhängigkeiten: verwendet ausschließlich stdlib-Module.
    """
    if not query or not query.strip():
        return ActionResult(success=False, message="Leere Suchanfrage.")

    encoded = urllib.parse.quote_plus(query.strip())
    url = f"https://html.duckduckgo.com/html/?q={encoded}&kl=de-de"

    try:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        log.exception("Websuche fehlgeschlagen")
        return ActionResult.from_exception(exc, message=f"Websuche fehlgeschlagen: {exc}")

    html_text = html.unescape(raw)

    title_matches = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    snippet_matches = re.findall(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )

    if not title_matches:
        return ActionResult(success=True, message="Keine Suchergebnisse gefunden.")

    lines: list[str] = []
    count = min(len(title_matches), len(snippet_matches), _MAX_RESULTS)
    for i in range(count):
        href, title = title_matches[i]
        title_clean = _strip_tags(html.unescape(title))
        snippet_clean = _strip_tags(html.unescape(snippet_matches[i]))
        real_url = _decode_ddg_link(html.unescape(href))
        lines.append(f"{i + 1}. {title_clean}\n   URL: {real_url}\n   {snippet_clean}")

    message = "Websuchergebnisse:\n\n" + "\n\n".join(lines)
    return ActionResult(success=True, message=message, details={"result_count": count})


_FETCH_MAX_CHARS = 6000  # bounded excerpt, not the whole page - keeps tool results token-cheap


def fetch_webpage(url: str) -> ActionResult:
    """Ruft eine URL serverseitig ab und gibt den bereinigten Lesetext zurück
    - kein sichtbares Browserfenster, genauso wie ChatGPT/Gemini beim
    "Seite ansehen" die Seite selbst abrufen statt einen Browser zu öffnen.
    """
    if not url.startswith(("http://", "https://")):
        return ActionResult(success=False, message="Ungültige URL (nur http/https erlaubt).")

    try:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        log.exception("Seitenabruf fehlgeschlagen: %s", url)
        return ActionResult.from_exception(exc, message=f"Seitenabruf fehlgeschlagen: {exc}")

    # Script/style CONTENT (not just the surrounding tags) isn't readable
    # text and would otherwise pollute the extracted output - strip whole
    # blocks first, then strip remaining markup tags.
    without_scripts = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", raw, flags=re.IGNORECASE | re.DOTALL)
    text = html.unescape(_strip_tags(without_scripts))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()

    if not text:
        return ActionResult(
            success=False,
            message="Seite abgerufen, aber kein lesbarer Text gefunden (z.B. rein per JavaScript geladene Inhalte).",
        )

    truncated = len(text) > _FETCH_MAX_CHARS
    excerpt = text[:_FETCH_MAX_CHARS]
    message = f"Inhalt von {url}:\n\n{excerpt}"
    if truncated:
        message += "\n\n[... gekürzt, Seite ist länger ...]"

    return ActionResult(success=True, message=message, details={"truncated": truncated, "length": len(text)})


def open_browser(url: str) -> ActionResult:
    """Öffnet eine URL im Standard-Browser."""
    if not url.startswith(("http://", "https://")):
        return ActionResult(success=False, message="Ungültige URL (nur http/https erlaubt).")

    try:
        webbrowser.open(url)
        log.info("Browser geöffnet: %s", url)
        return ActionResult(success=True, message=f"Browser geöffnet mit: {url}")
    except Exception as exc:
        log.exception("Browser-Fehler")
        return ActionResult.from_exception(exc, message=f"Browser-Fehler: {exc}")
