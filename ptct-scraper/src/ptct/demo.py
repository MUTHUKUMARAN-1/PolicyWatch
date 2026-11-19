"""Scripted, fully offline refresh scenario (3+ timestamped cycles + the CP-5 private-test pattern).

Cycle  Day  acme-privacy                          acme-terms
  1     0   baseline v1                            baseline v1
  2     1   v2 (edit + new section) -> alerts      v2 (edit) -> alerts
  3     2   identical -> duplicate suppressed      identical -> duplicate suppressed
  4     3   HTTP 404 -> fetch_error (NO deletion)  identical
  5     4   page restored (same content)           formatting-only edit -> format_only, no alert
  6     5   formatting-only edit                   identical
  7     6   selector renamed -> parser_failure     identical
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .fetcher import OfflineFetcher
from .runner import RunLog, run_once
from .storage import Storage

FIX = Path(__file__).resolve().parent.parent.parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def scenario() -> list[dict[str, tuple[int, str]]]:
    p1, p2, p2f, pbad = (_read(n) for n in ("demo_privacy_v1.html", "demo_privacy_v2.html",
                                           "demo_privacy_v2_format.html", "demo_privacy_selector_changed.html"))
    t1, t2, tf = _read("terms_v1.html"), _read("terms_v2.html"), _read("terms_format_only.html")
    return [
        {"acme-privacy": (200, p1), "acme-terms": (200, t1)},
        {"acme-privacy": (200, p2), "acme-terms": (200, t2)},
        {"acme-privacy": (200, p2), "acme-terms": (200, t2)},
        {"acme-privacy": (404, ""), "acme-terms": (200, t2)},
        {"acme-privacy": (200, p2), "acme-terms": (200, tf)},
        {"acme-privacy": (200, p2f), "acme-terms": (200, tf)},
        {"acme-privacy": (200, pbad), "acme-terms": (200, tf)},
    ]


def run_demo(settings: Settings, storage: Storage, runlog: RunLog | None = None):
    start = datetime(2026, 11, 1, 9, 0, 0, tzinfo=timezone.utc)
    summaries = []
    for i, cycle in enumerate(scenario()):
        script = {s.url: [cycle[s.id]] for s in settings.sources}
        clock_time = start + timedelta(days=i)
        summaries.append(run_once(settings, OfflineFetcher(script), storage, live=False,
                                  clock=lambda t=clock_time: t, runlog=runlog))
    return summaries
