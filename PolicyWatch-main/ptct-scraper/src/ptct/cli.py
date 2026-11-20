"""Command-line interface.

  python -m ptct.cli validate-config
  python -m ptct.cli run --offline          # serve each source's fixture file
  python -m ptct.cli run --live             # APPROVED sources only; respectful requester
  python -m ptct.cli demo                   # 7 scripted refresh cycles incl. 404 / restore / format-only / selector break
  python -m ptct.cli status                 # freshness + stale warnings
  python -m ptct.cli export                 # CSVs to data/exports/
  python -m ptct.cli review --id 3 --status confirmed --by midhun --note "verified on site"
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .demo import run_demo
from .exporter import export_all
from .fetcher import Fetcher, OfflineFetcher, RobotsPolicy
from .runner import RunLog, freshness, run_once
from .storage import Storage


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ptct", description="Privacy Policy & Terms Change Tracker - collector")
    ap.add_argument("--config", default="config/sources.yaml")
    ap.add_argument("--db", default="data/ptct.db")
    ap.add_argument("--snapshots", default="data/snapshots")
    ap.add_argument("--log", default="logs/run_log.jsonl")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate-config")
    r = sub.add_parser("run")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--live", action="store_true")
    g.add_argument("--offline", action="store_true")
    sub.add_parser("demo")
    sub.add_parser("status")
    sub.add_parser("export").add_argument("--out", default="data/exports")
    rv = sub.add_parser("review")
    rv.add_argument("--id", type=int, required=True)
    rv.add_argument("--status", required=True, choices=["confirmed", "dismissed", "pending"])
    rv.add_argument("--by", required=True)
    rv.add_argument("--note", default="")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(message)s")

    try:
        settings = load_config(a.config)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 2
    if a.cmd == "validate-config":
        print(f"OK: {len(settings.sources)} sources ({len(settings.live_sources())} approved for live collection)")
        return 0

    storage = Storage(a.db, a.snapshots)
    runlog = RunLog(a.log)
    try:
        if a.cmd == "run":
            if a.live:
                if "YOUR_EMAIL_HERE" in settings.user_agent:
                    print("Set a real contact e-mail in crawl.user_agent before live collection.", file=sys.stderr)
                    return 2
                if not settings.live_sources():
                    print("No APPROVED sources. Get written mentor approval, then set approval_status: APPROVED.",
                          file=sys.stderr)
                    return 2
                robots = RobotsPolicy(settings.user_agent, timeout=settings.timeout)
                fetcher = Fetcher(settings.user_agent, settings.timeout, settings.min_interval,
                                  settings.max_retries, settings.backoff_base, robots=robots)
            else:
                script = {s.url: [(200, Path(s.fixture).read_text(encoding="utf-8"))]
                          for s in settings.sources if s.fixture}
                fetcher = OfflineFetcher(script)
            s = run_once(settings, fetcher, storage, live=a.live, runlog=runlog)
            print(f"{s.run_id}: attempted={s.attempted} ok={s.parsed_ok} parse_failed={s.parsed_failed} "
                  f"fetch_failed={s.fetch_failed} new_versions={s.new_versions} alerts={s.alerts} dup={s.duplicates}")
        elif a.cmd == "demo":
            for i, s in enumerate(run_demo(settings, storage, runlog), 1):
                print(f"cycle {i}: {s.run_id} ok={s.parsed_ok} parse_failed={s.parsed_failed} "
                      f"fetch_failed={s.fetch_failed} new_versions={s.new_versions} alerts={s.alerts} dup={s.duplicates}")
        elif a.cmd == "status":
            for f in freshness(settings, storage):
                print(f)
        elif a.cmd == "export":
            for p in export_all(storage, a.out):
                print("wrote", p)
        elif a.cmd == "review":
            storage.review(a.id, a.status, a.by, a.note)
            print(f"change {a.id} -> {a.status}")
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
