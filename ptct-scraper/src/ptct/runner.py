"""One refresh cycle: fetch -> parse -> validate -> version -> classify changes -> log."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from .config import Settings, Source
from .differ import diff_versions
from .parser import ParserError, parse_policy
from .storage import Storage
from .timeutil import iso, parse_iso, utc_now
from .validator import validate

log = logging.getLogger("ptct")


@dataclass
class RunSummary:
    run_id: str
    attempted: int = 0
    parsed_ok: int = 0
    parsed_failed: int = 0
    fetch_failed: int = 0
    new_versions: int = 0
    alerts: int = 0
    duplicates: int = 0
    events: list[dict] = field(default_factory=list)

    def counts(self) -> dict:
        return {k: getattr(self, k) for k in
                ("attempted", "parsed_ok", "parsed_failed", "fetch_failed", "new_versions", "alerts", "duplicates")}


class RunLog:
    """Append-only JSON-lines observability log (last attempted/successful run, parsed/failed items, ...)."""

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        log.info("%s", json.dumps(record, ensure_ascii=False))
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_once(settings: Settings, fetcher, storage: Storage, *, live: bool, clock=utc_now,
             runlog: RunLog | None = None, sources: list[Source] | None = None) -> RunSummary:
    runlog = runlog or RunLog(None)
    started = clock()
    run_id = f"run-{started.strftime('%Y%m%dT%H%M%S')}"
    n = 1
    while storage.rows("SELECT 1 FROM runs WHERE run_id=?", (run_id,)):
        n += 1
        run_id = f"run-{started.strftime('%Y%m%dT%H%M%S')}-{n}"
    storage.start_run(run_id, iso(started), "live" if live else "offline")
    summary = RunSummary(run_id)

    todo = sources if sources is not None else (settings.live_sources() if live else settings.sources)
    for src in todo[: settings.max_pages_per_run]:
        summary.attempted += 1
        _process(src, settings, fetcher, storage, summary, clock, runlog)

    storage.finish_run(run_id, iso(clock()), summary.counts())
    return summary


def _event(runlog, summary, src, attempted_at, **kw):
    rec = {"run_id": summary.run_id, "source_id": src.id, "url": src.url, "last_attempted": attempted_at, **kw}
    summary.events.append(rec)
    runlog.write(rec)


def _process(src, settings, fetcher, storage, summary, clock, runlog):
    res = fetcher.fetch(src.url)
    attempted = iso(clock())  # use the (injectable) run clock so refresh cycles are reproducible
    run_id = summary.run_id
    prev = storage.latest_version(src.id)

    # ---- 1. fetch failed: record, keep old data, NEVER treat as deletion
    if not res.ok:
        storage.add_snapshot(run_id=run_id, source_id=src.id, url=src.url, fetched_at=attempted,
                             fetch_status=res.status, http_code=res.http_code, error=res.error)
        storage.update_state(src.id, attempted, False, res.status, res.error)
        storage.add_change(run_id=run_id, source_id=src.id, url=src.url, detected_at=attempted,
                           category="fetch_error", is_alert=False, section=None,
                           before=None, after=f"{res.status} (HTTP {res.http_code}): {res.error}",
                           from_version=prev["version_no"] if prev else None, key_extra=run_id)
        summary.fetch_failed += 1
        _event(runlog, summary, src, attempted, status=res.status, http_code=res.http_code,
               parsed_items=0, failed_items=1, retry_after=res.retry_after, error=res.error,
               last_successful=(storage.state(src.id)["last_success"]))
        return

    raw_hash, raw_path = storage.save_raw(src.id, attempted, res.text)

    # ---- 2. parse + validate
    try:
        doc = parse_policy(res.text, src.selectors)
        v = validate(doc, settings.min_body_chars, prev_chars=_prev_chars(prev))
        if not v.ok:
            raise ParserError(v.errors[0], ", ".join(v.errors))
    except ParserError as e:
        snap = storage.add_snapshot(run_id=run_id, source_id=src.id, url=src.url, fetched_at=attempted,
                                    fetch_status="ok", http_code=res.http_code, raw_hash=raw_hash,
                                    raw_path=raw_path, parse_status="failed", error=str(e))
        storage.update_state(src.id, attempted, False, "parser_failure", str(e))
        storage.add_change(run_id=run_id, source_id=src.id, url=src.url, detected_at=attempted,
                           category="parser_failure", is_alert=False, section=None, before=None,
                           after=f"{e.code}: {e.detail}", from_version=prev["version_no"] if prev else None,
                           key_extra=run_id)
        summary.parsed_failed += 1
        _event(runlog, summary, src, attempted, status="parser_failure", http_code=res.http_code,
               parsed_items=0, failed_items=1, selector_issue=e.code, error=str(e),
               last_successful=(storage.state(src.id)["last_success"]), raw_path=raw_path)
        return

    snap = storage.add_snapshot(run_id=run_id, source_id=src.id, url=src.url, fetched_at=attempted,
                                fetch_status="ok", http_code=res.http_code, raw_hash=raw_hash,
                                raw_path=raw_path, parse_status="ok")
    summary.parsed_ok += 1

    # ---- 3. version / classify
    alerts = 0
    outcome = "baseline"
    if prev is None:
        storage.add_version(src.id, 1, attempted, doc, raw_hash, snap)
        storage.add_change(run_id=run_id, source_id=src.id, url=src.url, detected_at=attempted,
                           category="baseline", is_alert=False, after=f"{len(doc.sections)} sections captured",
                           to_version=1)
        summary.new_versions += 1
    elif prev["content_hash"] == doc.content_hash:
        outcome = "unchanged"
        summary.duplicates += 1
        if prev["last_raw_hash"] != raw_hash:
            outcome = "format_only"
            storage.add_change(run_id=run_id, source_id=src.id, url=src.url, detected_at=attempted,
                               category="format_only", is_alert=False, before=prev["last_raw_hash"][:12],
                               after=raw_hash[:12], from_version=prev["version_no"], to_version=prev["version_no"])
        storage.touch_version(prev["id"], attempted, raw_hash)
    else:
        outcome = "changed"
        old_doc = json.loads(prev["doc_json"])
        new_no = prev["version_no"] + 1
        storage.add_version(src.id, new_no, attempted, doc, raw_hash, snap)
        summary.new_versions += 1
        for ch in diff_versions(old_doc, doc):
            inserted = storage.add_change(run_id=run_id, source_id=src.id, url=src.url, detected_at=attempted,
                                          category=ch.category, is_alert=ch.is_alert, section=ch.section,
                                          before=ch.before, after=ch.after,
                                          from_version=prev["version_no"], to_version=new_no)
            if inserted and ch.is_alert:
                alerts += 1
            elif not inserted:
                summary.duplicates += 1
        summary.alerts += alerts

    storage.update_state(src.id, attempted, True, "ok", None)
    _event(runlog, summary, src, attempted, status="ok", http_code=res.http_code, outcome=outcome,
           parsed_items=len(doc.sections), failed_items=0, alerts=alerts, warnings=v.warnings,
           last_successful=attempted, update_age_hours=0.0, raw_path=raw_path)


def _prev_chars(prev) -> int | None:
    if prev is None:
        return None
    d = json.loads(prev["doc_json"])
    return sum(len(s["text"]) for s in d["sections"])


def freshness(settings: Settings, storage: Storage, now=None) -> list[dict]:
    """Per-source freshness: last attempted vs last successful refresh and a stale-data warning."""
    now = now or utc_now()
    out = []
    for s in settings.sources:
        st = storage.state(s.id)
        if st is None or not st["last_success"]:
            out.append({"source_id": s.id, "last_attempted": st["last_attempted"] if st else None,
                        "last_success": None, "age_hours": None, "stale": True,
                        "status": st["last_status"] if st else "never_run",
                        "warning": "No successful refresh yet - data unavailable"})
            continue
        age = (now - parse_iso(st["last_success"])) / timedelta(hours=1)
        stale = age > 2 * s.refresh_hours
        out.append({"source_id": s.id, "last_attempted": st["last_attempted"], "last_success": st["last_success"],
                    "age_hours": round(age, 1), "stale": stale, "status": st["last_status"],
                    "warning": (f"STALE: last successful refresh {age:.0f}h ago (expected every {s.refresh_hours}h)"
                                if stale else "")})
    return out
