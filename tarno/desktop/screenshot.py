"""Screenshot capture."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def take_screenshot(save_path: str | None = None) -> str:
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Screenshot nicht verfügbar (Pillow nicht installiert)."

    try:
        img = ImageGrab.grab()
        if save_path is None:
            # KERNFIX (Code-Review): vorher pro Aufruf eine NEUE, eindeutige
            # Temp-Datei ohne jede Aufraeumung (delete=False) - bei einem
            # Dauerlauf-Assistenten, der dieses Tool ueber Tage/Wochen
            # wiederholt aufruft (z.B. via describe_what_i_see), sammelten
            # sich unbegrenzt viele verwaiste PNGs im Temp-Ordner an. Fester
            # Dateiname statt eindeutigem Namen: der vorherige Screenshot wird
            # ohnehin nicht mehr gebraucht, sobald ein neuer angefordert wird -
            # dadurch bleibt immer hoechstens EINE Datei liegen, nicht immer
            # mehr. Wer bewusst mehrere behalten will, gibt explizit einen
            # eigenen save_path an (unveraendertes Verhalten).
            save_path = str(Path(tempfile.gettempdir()) / "tarno_screenshot.png")

        img.save(save_path)
        log.info("Screenshot gespeichert: %s", save_path)
        return f"Screenshot gespeichert: {save_path}"
    except Exception as exc:
        return f"Screenshot-Fehler: {exc}"
