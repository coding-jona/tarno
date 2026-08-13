"""Accelerated soak-test harness for TARNO's core loops (Block 6, Phasen 57-59).

Not a pytest test - designed to run standalone for extended periods (the
literal 24h the masterplan calls for) to catch slow memory leaks that a
short unit test can't. Exercises the conversation/memory write-and-retrieve
cycle and the ProactiveEngine tick loop (Block 3) under tight repetition,
periodically sampling RSS memory via psutil and reporting a growth trend.

This does NOT measure real audio/LLM/TTS latency (that needs the actual app
running live with you interacting - see the Block 6 planning notes) - it is
specifically a memory-leak smoke test for the background-loop machinery.

Usage:
    py -3.12 workspace/debug/tools/soak_test.py --duration-seconds 60 --sample-interval 5
    py -3.12 workspace/debug/tools/soak_test.py --duration-seconds 86400 --sample-interval 300  # real 24h run
"""

from __future__ import annotations

import argparse
import gc
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))

import psutil  # noqa: E402

from tarno_backend.ai.conversation import ConversationManager  # noqa: E402
from tarno_backend.core.config import MemoryConfig  # noqa: E402
from tarno_backend.core.proactive_engine import ProactiveDraft, ProactiveEngine  # noqa: E402
from tarno_backend.memory.store import MemoryStore  # noqa: E402


class _CyclingObserver:
    """Synthetic observer for the soak test - returns a draft on a fixed
    cadence rather than depending on real OS/calendar state, so the test
    isolates the ENGINE's own memory behavior (cooldown dict, etc.) rather
    than re-testing the real observers (already covered in
    tests/test_proactive_engine.py)."""

    name = "soak_synthetic"

    def __init__(self) -> None:
        self._counter = 0

    def check(self) -> ProactiveDraft | None:
        self._counter += 1
        if self._counter % 3 != 0:
            return None
        return ProactiveDraft(
            source=self.name,
            message=f"Synthetischer Trigger #{self._counter}",
            score=95,
        )


def _run_conversation_cycle(conversation: ConversationManager, memory_store: MemoryStore, iteration: int) -> None:
    conversation.add_user_message(f"Testnachricht {iteration}")
    conversation.add_assistant_response(f"Testantwort {iteration}")
    # Bounded key space (mod 20): simulates realistic fact updates/overwrites
    # rather than unbounded key growth, which would trivially "leak" by
    # design and defeat the point of a leak test.
    conversation.remember_fact(f"testfakt_{iteration % 20}", f"wert_{iteration}")
    conversation.inject_relevant_memory(f"Testnachricht {iteration}")


def run_soak_test(duration_seconds: float, sample_interval_seconds: float) -> int:
    process = psutil.Process()

    with tempfile.TemporaryDirectory() as tmp:
        memory_store = MemoryStore(Path(tmp) / "soak_memory.db")
        conversation = ConversationManager(
            max_history=20,
            memory=MemoryConfig(enabled=True, storage_dir=tmp),
            memory_store=memory_store,
        )

        triggered_count = 0

        def on_trigger(draft: ProactiveDraft) -> None:
            nonlocal triggered_count
            triggered_count += 1

        engine = ProactiveEngine(
            observers=[_CyclingObserver()],
            on_trigger=on_trigger,
            tick_seconds=0.01,  # accelerated - real config uses 10s
            score_threshold=85,
            source_cooldown_seconds=0.05,  # accelerated - real default is 300s
        )

        samples: list[tuple[int, float]] = []
        start = time.monotonic()
        next_sample_at = start + sample_interval_seconds
        iteration = 0

        print(f"Soak-Test gestartet: {duration_seconds:.0f}s Laufzeit, Sample alle {sample_interval_seconds:.0f}s")
        print(f"{'Iterationen':>12} | {'Zeit (s)':>10} | {'RSS (MB)':>10} | Proaktive Trigger")

        while time.monotonic() - start < duration_seconds:
            _run_conversation_cycle(conversation, memory_store, iteration)
            engine._check_one(engine._observers[0])  # noqa: SLF001 - direct tick, no real thread/sleep needed

            now = time.monotonic()
            if now >= next_sample_at:
                gc.collect()
                rss_mb = process.memory_info().rss / (1024 * 1024)
                elapsed = now - start
                samples.append((iteration, rss_mb))
                print(f"{iteration:>12} | {elapsed:>10.1f} | {rss_mb:>10.1f} | {triggered_count}")
                next_sample_at += sample_interval_seconds

            iteration += 1

        memory_store.close()

    return _report_growth(samples)


def _report_growth(samples: list[tuple[int, float]]) -> int:
    """Compare average RSS of the first half of samples vs. the second half.
    Returns 0 (OK) or 1 (possible leak) as a process exit code."""
    if len(samples) < 4:
        print("\nZu wenige Samples für eine Trend-Aussage (Laufzeit zu kurz).")
        return 0

    mid = len(samples) // 2
    first_half_avg = sum(rss for _, rss in samples[:mid]) / mid
    second_half_avg = sum(rss for _, rss in samples[mid:]) / (len(samples) - mid)
    growth_mb = second_half_avg - first_half_avg
    growth_pct = (growth_mb / first_half_avg * 100) if first_half_avg > 0 else 0.0

    print(f"\nRSS erste Hälfte:  {first_half_avg:.1f} MB")
    print(f"RSS zweite Hälfte: {second_half_avg:.1f} MB")
    print(f"Wachstum:          {growth_mb:+.1f} MB ({growth_pct:+.1f}%)")

    # A few MB of drift is normal (allocator fragmentation, one-time caches
    # like the embedding model warming up) - flag only sustained, sizeable growth.
    if growth_pct > 20.0 and growth_mb > 10.0:
        print("\n[WARNUNG] Möglicher Memory-Leak: RSS wächst deutlich über die Laufzeit.")
        return 1

    print("\n[OK] Kein auffälliger Wachstumstrend.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duration-seconds", type=float, default=60.0, help="Gesamtlaufzeit (Default: 60s Smoke-Test; für den echten 24h-Test: 86400)")
    parser.add_argument("--sample-interval", type=float, default=5.0, help="Sekunden zwischen RSS-Messungen")
    args = parser.parse_args()

    return run_soak_test(args.duration_seconds, args.sample_interval)


if __name__ == "__main__":
    sys.exit(main())
