"""Labelled change-case evaluation (SRS section 9): >= 12 cases, false-alert quantification, before/after evidence."""
from __future__ import annotations

import csv
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .fetcher import OfflineFetcher
from .runner import run_once
from .storage import Storage

FIX = Path(__file__).resolve().parent.parent.parent / "fixtures"

# (name, description, steps[(http_code, fixture|None)], expected alert categories, expected non-alert events)
CASES = [
    ("01_no_change", "Identical page re-fetched", [(200, "privacy_v1.html")] * 2, set(), set()),
    ("02_whitespace_only", "Indentation / blank-line changes only", [(200, "privacy_v1.html"), (200, "privacy_whitespace_only.html")], set(), {"format_only"}),
    ("03_markup_only", "Extra wrapper div/span and new class names", [(200, "privacy_v1.html"), (200, "privacy_markup_only.html")], set(), {"format_only"}),
    ("04_cookie_banner_noise", "Cookie banner/nav added outside the policy body", [(200, "privacy_v1.html"), (200, "privacy_cookie_banner.html")], set(), {"format_only"}),
    ("05_curly_quotes_only", "Typographic apostrophe change only", [(200, "privacy_straight_quote.html"), (200, "privacy_curly_quote.html")], set(), {"format_only"}),
    ("06_wording_edit", "Retention period 30 -> 90 days", [(200, "privacy_v1.html"), (200, "privacy_retention_edit.html")], {"section_edited"}, set()),
    ("07_section_added", "New 'Children's Privacy' section", [(200, "privacy_v1.html"), (200, "privacy_section_added.html")], {"section_added"}, set()),
    ("08_section_removed", "'Sharing' section removed from a live page", [(200, "privacy_v1.html"), (200, "privacy_section_removed.html")], {"section_removed"}, set()),
    ("09_effective_date_only", "Only the 'last updated' date changes", [(200, "privacy_v1.html"), (200, "privacy_date_only.html")], {"date_changed"}, set()),
    ("10_title_changed", "Document title renamed", [(200, "privacy_v1.html"), (200, "privacy_title_changed.html")], {"title_changed"}, set()),
    ("11_multiple_changes", "Edit + new section + new date together", [(200, "privacy_v1.html"), (200, "privacy_multi_change.html")], {"section_edited", "section_added", "date_changed"}, set()),
    ("12_heading_renamed", "Heading renamed, body text identical", [(200, "privacy_v1.html"), (200, "privacy_heading_renamed.html")], {"section_renamed"}, set()),
    ("13_selector_changed", "Site renames the content container (selector break)", [(200, "privacy_v1.html"), (200, "privacy_selector_changed.html")], set(), {"parser_failure"}),
    ("14_empty_page", "HTTP 200 but empty body", [(200, "privacy_v1.html"), (200, "privacy_empty.html")], set(), {"parser_failure"}),
    ("15_http_404", "Page returns 404 - must NOT count as deletion", [(200, "privacy_v1.html"), (404, None)], set(), {"fetch_error"}),
    ("16_404_then_restored", "404 followed by restored identical page", [(200, "privacy_v1.html"), (404, None), (200, "privacy_v1.html")], set(), {"fetch_error"}),
    ("17_http_429", "Rate-limited (429) - stop, no change recorded", [(200, "privacy_v1.html"), (429, None)], set(), {"fetch_error"}),
]


def run_cases(settings: Settings) -> list[dict]:
    src = next(s for s in settings.sources if s.id == "acme-privacy")
    results = []
    for name, desc, steps, exp_alerts, exp_events in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            st = Storage(Path(tmp) / "t.db", Path(tmp) / "snaps")
            t0 = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
            for i, (code, fx) in enumerate(steps):
                html = (FIX / fx).read_text(encoding="utf-8") if fx else ""
                f = OfflineFetcher({src.url: [(code, html)]})
                t = t0 + timedelta(days=i)
                run_once(settings, f, st, live=False, clock=lambda t=t: t, sources=[src])
            rows = st.rows("SELECT * FROM changes WHERE category!='baseline' ORDER BY id")
            alerts = {r["category"] for r in rows if r["is_alert"]}
            events = {r["category"] for r in rows if not r["is_alert"]}
            vcount = st.rows("SELECT COUNT(*) c FROM versions")[0]["c"]
            ev = next((r for r in rows if r["is_alert"]), None)
            ok = alerts == exp_alerts and events == exp_events
            results.append({
                "case": name, "description": desc,
                "expected_alerts": ";".join(sorted(exp_alerts)) or "none",
                "actual_alerts": ";".join(sorted(alerts)) or "none",
                "expected_events": ";".join(sorted(exp_events)) or "none",
                "actual_events": ";".join(sorted(events)) or "none",
                "versions_stored": vcount,
                "false_alert": bool(alerts and not exp_alerts),
                "missed_alert": bool(exp_alerts - alerts),
                "pass": ok,
                "before_evidence": (ev["before_text"] or "")[:160] if ev else "",
                "after_evidence": (ev["after_text"] or "")[:160] if ev else "",
            })
            st.close()
    return results


def summarise(results: list[dict]) -> dict:
    n = len(results)
    negatives = [r for r in results if r["expected_alerts"] == "none"]
    positives = [r for r in results if r["expected_alerts"] != "none"]
    return {
        "cases": n, "passed": sum(r["pass"] for r in results),
        "accuracy_pct": round(100 * sum(r["pass"] for r in results) / n, 1),
        "negative_cases": len(negatives), "false_alerts": sum(r["false_alert"] for r in negatives),
        "false_alert_rate_pct": round(100 * sum(r["false_alert"] for r in negatives) / max(1, len(negatives)), 1),
        "positive_cases": len(positives), "missed_alerts": sum(r["missed_alert"] for r in positives),
    }


def write_csv(results: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
