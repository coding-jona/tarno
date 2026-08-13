"""Mistral vision API integration (Block 7, Phasen 65-66).

CORRECTION (2026-07-19, discovered while implementing this): the masterplan's
Phase 65 originally called for "pixtral-large-latest" as a standalone vision
model, based on research suggesting Mistral's text models didn't support
image input. Verified against the live API while building this: that model
ID no longer exists in Mistral's lineup, and mistral-small/medium/large-latest
all now accept image_url content blocks directly on the standard
chat/completions endpoint - Mistral has folded vision into their flagship
chat models rather than keeping a separate Pixtral line. This module still
exists as a separate path from MistralProvider's text-tiering
(tarno/ai/mistral_client.py) because a vision call is a distinct, deliberate,
infrequent action (a proactive trigger, not every chat turn) with its own
frame-selection prompt (Phase 66) - the model, not code heuristics, decides
which candidate frame matters and whether a reaction is warranted at all.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

import numpy as np

from tarno.vision.preprocessing import downscale_and_encode_jpeg, frame_to_data_url

log = logging.getLogger(__name__)

_BASE_URL = "https://api.mistral.ai/v1"

_FRAME_SELECTION_PROMPT = (
    "Du bekommst mehrere Kamera-Frames aus einem kurzen Bewegungsfenster, in "
    "zeitlicher Reihenfolge nummeriert (Frame 0 zuerst). Wähle das EINE "
    "Frame, das das Ereignis am klarsten zeigt, und entscheide, ob eine "
    "Reaktion gegenüber dem Nutzer überhaupt gerechtfertigt ist - nicht jede "
    "Bewegung ist relevant (ein vorbeilaufendes Haustier, Lichtschwankungen "
    "oder normale Alltagsbewegung meist nicht; eine fremde Person, ein "
    "Sturz, eine offensichtliche Notlage oder etwas eindeutig Ungewöhnliches "
    "eher). Antworte AUSSCHLIESSLICH als JSON-Objekt, keine Erklärung davor "
    "oder danach, mit genau diesen Feldern: "
    '"frame_index" (int, 0-basiert, welches Frame gemeint ist), '
    '"relevant" (bool, ob TARNO reagieren sollte), '
    '"reason" (kurzer deutscher Satz, was zu sehen ist), '
    '"score" (int 0-100, wie dringend/wichtig eine Reaktion wäre).'
)

_DESCRIBE_FRAME_PROMPT = (
    "Du bist eine präzise Bildanalyse-Einheit. Erstelle eine detaillierte, "
    "sachliche Inventur dieses Kamera-Standbilds. Beschreibe in 5-10 deutschen "
    "Sätzen: alle sichtbaren Objekte und Personen, deren ungefähre Position "
    "(links/rechts/vorne/hinten/Mitte), erkennbare Farben, Formen, Materialien "
    "und auffällige Details. Nenne nur Dinge, deren Präsenz du dir ziemlich "
    "sicher bist; markiere Unsicheres als 'unklar'. Vermeide: Emotionen, "
    "Intentionen, Interpretationen, spekulative Vermutungen. Beispiel: 'In der "
    "Mitte sitzt eine Person vor zwei Monitoren. Links ein kleinerer, rechts ein "
    "größerer Monitor. Auf dem Tisch zentral Tastatur und Maus. Links daneben "
    "steht eine Wasserflasche. Der Hintergrund ist dunkel und unscharf.'"
)


@dataclass(frozen=True)
class VisionAssessment:
    frame_index: int
    relevant: bool
    reason: str
    score: int


class MistralVisionProvider:
    """Sends candidate frames to a vision-capable Mistral model for
    frame-selection + relevance scoring."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "mistral-large-latest",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("MISTRAL_API_KEY", "")
        self._model = model
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def assess_frames(
        self, frames: list[np.ndarray], max_edge: int = 640, jpeg_quality: int = 80,
    ) -> VisionAssessment | None:
        """Send candidate frames to the vision model; it picks the most relevant one
        and scores it. Returns None on any failure or if unavailable - the
        caller (VisionObserver) treats that as "nothing to report", never a
        crash of the wider ProactiveEngine loop."""
        if not self.available or not frames:
            return None

        content: list[dict[str, object]] = [{"type": "text", "text": _FRAME_SELECTION_PROMPT}]
        for frame in frames:
            content.append({
                "type": "image_url",
                "image_url": frame_to_data_url(frame, max_edge, jpeg_quality),
            })

        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 300,
            "temperature": 0.2,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{_BASE_URL}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result = json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            log.exception("Vision-Anfrage fehlgeschlagen")
            return None
        except Exception:
            log.exception("Unerwarteter Fehler bei der Vision-Anfrage")
            return None

        return self._parse(result, len(frames))

    def describe_frame(self, frame: np.ndarray, max_edge: int = 640, jpeg_quality: int = 80) -> tuple[str, bytes] | None:
        """Describes a single on-demand frame in plain German prose - used by
        the 'describe_what_i_see' tool for direct user queries ("was siehst
        du?"), as opposed to assess_frames()'s JSON-scored relevance
        judgement for the autonomous motion-triggered path. Returns None on
        any failure or if unavailable, same contract as assess_frames().

        Returns a tuple of (description, jpeg_bytes) so the exact frame sent
        to the vision model can be displayed in the UI as an attachment.
        """
        if not self.available:
            return None

        import time

        jpeg_bytes = downscale_and_encode_jpeg(frame, max_edge, jpeg_quality)
        b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        image_url = f"data:image/jpeg;base64,{b64}"

        log.info(
            "Vision-Anfrage: model=%s, frame=%dx%d, jpeg=%d Bytes, timestamp=%.3f",
            self._model, frame.shape[1], frame.shape[0], len(jpeg_bytes), time.time(),
        )

        payload = {
            "model": self._model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": _DESCRIBE_FRAME_PROMPT},
                    {"type": "image_url", "image_url": image_url},
                ],
            }],
            "max_tokens": 200,
            "temperature": 0.2,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{_BASE_URL}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result = json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            log.exception("Vision-Beschreibungsanfrage fehlgeschlagen")
            return None
        except Exception:
            log.exception("Unerwarteter Fehler bei der Vision-Beschreibungsanfrage")
            return None

        try:
            description = result["choices"][0]["message"]["content"].strip()
            return description, jpeg_bytes
        except Exception:
            log.exception("Vision-Beschreibungsantwort konnte nicht geparst werden")
            return None

    @staticmethod
    def _parse(result: dict, frame_count: int) -> VisionAssessment | None:
        try:
            text = result["choices"][0]["message"]["content"].strip()
            # The model might wrap JSON in a code fence despite instructions
            # not to - strip defensively rather than fail the whole assessment.
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
            parsed = json.loads(text.strip())

            frame_index = int(parsed.get("frame_index", 0))
            if not (0 <= frame_index < frame_count):
                frame_index = 0

            return VisionAssessment(
                frame_index=frame_index,
                relevant=bool(parsed.get("relevant", False)),
                reason=str(parsed.get("reason", "")).strip(),
                score=max(0, min(100, int(parsed.get("score", 0)))),
            )
        except Exception:
            log.exception("Vision-Antwort konnte nicht geparst werden")
            return None
