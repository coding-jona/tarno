"""Autonomous trigger engine (Block 3, Phasen 21-30 des 70-Phasen-Masterplans).

Runs a lightweight background loop (Phase 21) that periodically polls a set of
Observers (Phasen 22-24, 29). Each Observer is its own rule-based relevance
classifier (TRACES-Prinzip, Phase 26) and pre-scores its own draft 0-100
before returning it - there is no separate cross-observer scoring step by
design (see the Block-3 planning discussion: a shared scorer would need to
compare unrelated domains like "CPU at 95%" vs. "meeting in 3 minutes" on one
scale, which a human-authored heuristic can't do meaningfully better than
letting each domain expert - the observer itself - already commit to a score).

Only when a draft's score exceeds the configured threshold (Phase 27) does the
engine invoke on_trigger() - and only once per source_cooldown_seconds per
observer (Phase 30), so a sustained condition (high RAM, an ongoing
distraction) can't retrigger TARNO's speech on every single tick and turn
into an endless loop.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from tarno_backend.core.calendar_service import CalendarService
    from tarno_backend.extensions.task_planner import TaskPlanner

log = logging.getLogger(__name__)


def clamp_score(value: float) -> int:
    """Clamp a raw score to the 0-100 integer range used throughout Block 3."""
    return max(0, min(100, round(value)))


@dataclass(frozen=True)
class ProactiveDraft:
    """A candidate autonomous action, already scored by its originating observer."""

    source: str  # observer name, used for cooldown bucketing and logging
    message: str  # what TARNO would say if this draft is triggered
    score: int  # 0-100, pre-computed by the observer (Phase 26)
    action: str | None = None  # optional follow-up tool action, e.g. "close_window"
    action_params: dict[str, Any] = field(default_factory=dict)


class ProactiveObserver(Protocol):
    """One autonomous background check, invoked every engine tick.

    Returns a scored draft, or None if nothing relevant changed since the
    last tick. Must never raise for expected "nothing to report" conditions -
    only for genuine failures (which ProactiveEngine logs and otherwise
    ignores, so one broken observer can't take down the whole loop).
    """

    name: str

    def check(self) -> ProactiveDraft | None: ...


class ProactiveEngine:
    """Phase 21: permanenter Background-Daemon-Loop.

    Polls all registered observers every tick_seconds. Debounces per-source
    (Phase 30) so a repeatedly-true condition doesn't retrigger every tick.
    """

    def __init__(
        self,
        observers: list[ProactiveObserver],
        on_trigger: Callable[[ProactiveDraft], None],
        tick_seconds: float = 10.0,
        score_threshold: int = 85,
        source_cooldown_seconds: float = 300.0,
    ) -> None:
        self._observers = list(observers)
        self._observers_lock = threading.Lock()
        self._on_trigger = on_trigger
        self._tick_seconds = tick_seconds
        self._score_threshold = score_threshold
        self._cooldown_seconds = source_cooldown_seconds
        self._last_triggered: dict[str, float] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def add_observer(self, observer: ProactiveObserver) -> None:
        """Attach an observer while the engine may already be running (e.g.
        Block 7's live camera opt-in, which can be requested at any time
        after startup, not just when TARNO first launches)."""
        with self._observers_lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def remove_observer(self, observer: ProactiveObserver) -> None:
        with self._observers_lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ProactiveEngine")
        self._thread.start()
        log.info(
            "ProactiveEngine gestartet (tick=%.0fs, threshold=%d, %d Observer)",
            self._tick_seconds, self._score_threshold, len(self._observers),
        )

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        log.info("ProactiveEngine gestoppt")

    def _run(self) -> None:
        while self._running and not self._stop_event.is_set():
            with self._observers_lock:
                observers_snapshot = list(self._observers)
            for observer in observers_snapshot:
                self._check_one(observer)
            if self._stop_event.wait(self._tick_seconds):
                break

    def _check_one(self, observer: ProactiveObserver) -> None:
        try:
            draft = observer.check()
        except Exception:
            log.exception("Observer %s fehlgeschlagen", getattr(observer, "name", observer))
            return
        if draft is None:
            return
        if draft.score <= self._score_threshold:
            log.debug(
                "Draft von %s unter Schwellenwert (%d <= %d), ignoriert",
                draft.source, draft.score, self._score_threshold,
            )
            return

        now = time.monotonic()
        last = self._last_triggered.get(draft.source)
        if last is not None and now - last < self._cooldown_seconds:
            log.debug(
                "Draft von %s im Cooldown (%.0fs verbleibend)",
                draft.source, self._cooldown_seconds - (now - last),
            )
            return

        self._last_triggered[draft.source] = now
        log.info("Proaktiver Trigger: %s (Score=%d): %s", draft.source, draft.score, draft.message)
        try:
            self._on_trigger(draft)
        except Exception:
            log.exception("on_trigger-Callback fehlgeschlagen für Quelle %s", draft.source)


class TimeCalendarObserver:
    """Phase 22: Zeit- & Termin-Observer.

    Drafts a heads-up when a calendar event starts within lookahead_minutes,
    scored higher the closer the event is (70-100 range). Each event is
    announced at most once (tracked by summary+start), not once per tick.
    """

    name = "calendar"

    def __init__(self, calendar_service: "CalendarService", lookahead_minutes: int = 15) -> None:
        self._calendar = calendar_service
        self._lookahead_minutes = max(1, lookahead_minutes)
        self._announced: set[str] = set()

    def check(self) -> ProactiveDraft | None:
        events = self._calendar.get_upcoming_events(days_ahead=1)
        now = datetime.now()

        for event in events:
            start = event.start
            if not isinstance(start, datetime):
                continue  # all-day events have no meaningful "minutes until"

            minutes_until = (start - now).total_seconds() / 60.0
            if not (0 <= minutes_until <= self._lookahead_minutes):
                continue

            key = f"{event.summary}@{start.isoformat()}"
            if key in self._announced:
                continue
            self._announced.add(key)

            urgency = 1.0 - (minutes_until / self._lookahead_minutes)
            score = clamp_score(70 + 30 * urgency)
            return ProactiveDraft(
                source=self.name,
                message=(
                    f"Ein Termin steht bevor, sir: \"{event.summary}\" "
                    f"in {max(0, int(minutes_until))} Minuten."
                ),
                score=score,
            )
        return None


class SystemObserver:
    """Phase 23: System- & Netzwerk-Observer (psutil-basiert).

    Bewusst ohne Docker-Container-Inspektion - das würde eine neue Abhängigkeit
    (docker-py o.ä.) einführen, die sonst nirgends im Projekt gebraucht wird.
    Port-Erreichbarkeits-Checks sind hier ebenfalls ausgeklammert (kein
    konfigurierter Anwendungsfall bisher); CPU/RAM/Disk-Schwellenwerte decken
    den in diesem Durchgang angeforderten Kern ab.
    """

    name = "system"

    def __init__(
        self,
        cpu_threshold: float = 90.0,
        ram_threshold: float = 90.0,
        disk_threshold: float = 90.0,
    ) -> None:
        self._cpu_threshold = cpu_threshold
        self._ram_threshold = ram_threshold
        self._disk_threshold = disk_threshold

    def check(self) -> ProactiveDraft | None:
        try:
            import psutil
        except ImportError:
            return None

        candidates: list[tuple[str, float, float]] = []  # (label, value, threshold)
        try:
            candidates.append(("CPU-Auslastung", psutil.cpu_percent(interval=None), self._cpu_threshold))
        except Exception:
            log.debug("CPU-Messung fehlgeschlagen", exc_info=True)
        try:
            candidates.append(("Arbeitsspeicher-Auslastung", psutil.virtual_memory().percent, self._ram_threshold))
        except Exception:
            log.debug("RAM-Messung fehlgeschlagen", exc_info=True)
        try:
            # KERNFIX (Code-Review): dieselbe "/"-Mehrdeutigkeit wie in
            # desktop/system_info.py - unter Windows misst psutil.disk_usage("/")
            # das Laufwerk des aktuellen Arbeitsverzeichnisses, nicht die
            # Systemplatte. Explizit %SystemDrive% verwenden, damit die
            # proaktive Warnung immer dieselbe (die vom Nutzer gemeinte) Platte
            # betrifft, unabhaengig vom Prozess-Arbeitsverzeichnis.
            import os as _os
            system_drive = _os.environ.get("SystemDrive", "C:") + "\\" if _os.name == "nt" else "/"
            candidates.append(("Festplatten-Auslastung", psutil.disk_usage(system_drive).percent, self._disk_threshold))
        except Exception:
            log.debug("Festplatten-Messung fehlgeschlagen", exc_info=True)

        # Report only the worst offender per tick to avoid stacking multiple
        # simultaneous warnings - the cooldown already limits repeat noise,
        # this limits *breadth* of a single trigger.
        worst: tuple[str, float, float] | None = None
        worst_overage = 0.0
        for label, value, threshold in candidates:
            if value <= threshold:
                continue
            overage = value - threshold
            if overage > worst_overage:
                worst_overage = overage
                worst = (label, value, threshold)

        if worst is None:
            return None

        label, value, threshold = worst
        score = clamp_score(60 + worst_overage * 2)
        return ProactiveDraft(
            source=self.name,
            message=(
                f"Ich würde anmerken, dass die {label} bei {value:.0f}% liegt, sir - "
                f"deutlich über dem Schwellenwert von {threshold:.0f}%."
            ),
            score=score,
        )


class UserBehaviorObserver:
    """Phase 24 (Basisverhalten) + Phase 28 (Anti-Ablenkungs-Exekutive).

    Tracks how long the active window has matched a configured "distraction"
    keyword. A sustained distraction alone drafts a gentle, moderate-score
    nudge. If a calendar event is imminent at the same time, the draft
    escalates to a high score and includes a close_window action - TARNO may
    then autonomously close the distracting window (gated through
    CommandEngine/PermissionService by the caller, see CommandTool.
    close_window_gated(), respecting the current AutonomyMode).
    """

    name = "user_behavior"

    def __init__(
        self,
        distraction_apps: list[str],
        calendar_service: "CalendarService",
        minutes_before_action: float = 5.0,
        calendar_lookahead_minutes: int = 15,
        close_distraction_window: bool = False,
    ) -> None:
        self._distraction_apps = [a.lower() for a in distraction_apps]
        self._calendar = calendar_service
        self._minutes_before_action = minutes_before_action
        self._calendar_lookahead_minutes = calendar_lookahead_minutes
        self._close_enabled = close_distraction_window
        self._distraction_since: datetime | None = None
        self._current_match: str | None = None

    def check(self) -> ProactiveDraft | None:
        from tarno_backend.desktop.window_manager import get_active_window

        window = get_active_window()
        title = str(window.get("title", "")).lower() if window else ""
        match = next((app for app in self._distraction_apps if app in title), None)

        now = datetime.now()
        if match is None:
            self._distraction_since = None
            self._current_match = None
            return None

        if match != self._current_match:
            self._current_match = match
            self._distraction_since = now
            return None

        assert self._distraction_since is not None
        distracted_minutes = (now - self._distraction_since).total_seconds() / 60.0
        if distracted_minutes < self._minutes_before_action:
            return None

        imminent_event = self._imminent_event_summary(now)
        if imminent_event is None:
            # Baseline nudge (Phase 24): noticeable but not urgent.
            return ProactiveDraft(
                source=self.name,
                message=(
                    f"Sie beschäftigen sich nun seit {int(distracted_minutes)} Minuten mit "
                    f"'{match}', sir. Nur zur Kenntnisnahme."
                ),
                score=clamp_score(50 + min(distracted_minutes, 10)),
            )

        # Escalation (Phase 28): distraction + an imminent event overlap.
        message = (
            f"Sir, in Kürze steht \"{imminent_event}\" an, während Sie seit "
            f"{int(distracted_minutes)} Minuten mit '{match}' beschäftigt sind."
        )
        action, action_params = None, {}
        if self._close_enabled and window is not None:
            message += " Ich schließe das ablenkende Fenster."
            action = "close_window"
            action_params = {"title_substring": str(window.get("title", match))}
        return ProactiveDraft(
            source=self.name,
            message=message,
            score=95,
            action=action,
            action_params=action_params,
        )

    def _imminent_event_summary(self, now: datetime) -> str | None:
        for event in self._calendar.get_upcoming_events(days_ahead=1):
            if not isinstance(event.start, datetime):
                continue
            minutes_until = (event.start - now).total_seconds() / 60.0
            if 0 <= minutes_until <= self._calendar_lookahead_minutes:
                return event.summary
        return None


class IdleCuriosityObserver:
    """Phase 29: "Iterative Neugier".

    Wenn der Nutzer seit idle_minutes_for_curiosity nicht mehr mit TARNO
    interagiert hat und offene, unvollständige Aufgaben (TaskPlanner) existieren,
    fragt TARNO proaktiv nach Vervollständigung statt stillschweigend zu warten.
    """

    name = "idle_curiosity"

    def __init__(
        self,
        task_planner: "TaskPlanner",
        get_last_interaction: Callable[[], datetime],
        idle_minutes: float = 15.0,
    ) -> None:
        self._task_planner = task_planner
        self._get_last_interaction = get_last_interaction
        self._idle_minutes = idle_minutes

    def check(self) -> ProactiveDraft | None:
        last_interaction = self._get_last_interaction()
        idle_minutes = (datetime.now() - last_interaction).total_seconds() / 60.0
        if idle_minutes < self._idle_minutes:
            return None

        pending = self._task_planner.list_pending()
        if not pending:
            return None

        oldest = min(pending, key=lambda t: t.created_at)
        return ProactiveDraft(
            source=self.name,
            message=(
                f"Da Sie ohnehin gerade nicht beschäftigt sind, sir - die Aufgabe "
                f"\"{oldest.description}\" wartet noch auf Ihre Entscheidung."
            ),
            score=88,
        )
