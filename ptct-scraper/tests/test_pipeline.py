"""End-to-end pipeline behaviour, including the SRS CP-5 private-test pattern."""
from datetime import datetime, timedelta, timezone

from ptct.fetcher import OfflineFetcher
from ptct.runner import freshness, run_once
from ptct.validator import validate
from ptct.parser import parse_policy

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


def cycle(settings, storage, src, code, html, day):
    t = T0 + timedelta(days=day)
    return run_once(settings, OfflineFetcher({src.url: [(code, html)]}), storage, live=False,
                    clock=lambda: t, sources=[src])


def src_of(settings, sid="acme-privacy"):
    return next(s for s in settings.sources if s.id == sid)


def test_rerun_is_idempotent_no_duplicate_inflation(settings, storage, fx):
    src = src_of(settings)
    for d in range(3):
        cycle(settings, storage, src, 200, fx("privacy_v1.html"), d)
    assert storage.rows("SELECT COUNT(*) c FROM versions")[0]["c"] == 1
    assert storage.rows("SELECT last_seen FROM versions")[0]["last_seen"].startswith("2026-11-03")
    assert storage.rows("SELECT COUNT(*) c FROM changes WHERE is_alert=1")[0]["c"] == 0


def test_cp5_404_restore_format_edit_no_false_alerts(settings, storage, fx):
    src = src_of(settings)
    cycle(settings, storage, src, 200, fx("privacy_v1.html"), 0)
    s404 = cycle(settings, storage, src, 404, "", 1)
    assert s404.fetch_failed == 1 and s404.alerts == 0
    assert storage.rows("SELECT COUNT(*) c FROM changes WHERE category='section_removed'")[0]["c"] == 0
    restored = cycle(settings, storage, src, 200, fx("privacy_v1.html"), 2)
    assert restored.alerts == 0
    fmt = cycle(settings, storage, src, 200, fx("privacy_markup_only.html"), 3)
    assert fmt.alerts == 0 and fmt.new_versions == 0
    assert storage.rows("SELECT COUNT(*) c FROM changes WHERE is_alert=1")[0]["c"] == 0
    assert storage.rows("SELECT COUNT(*) c FROM versions")[0]["c"] == 1


def test_real_change_creates_version_and_alert(settings, storage, fx):
    src = src_of(settings)
    cycle(settings, storage, src, 200, fx("privacy_v1.html"), 0)
    s = cycle(settings, storage, src, 200, fx("privacy_retention_edit.html"), 1)
    assert s.alerts == 1 and s.new_versions == 1
    row = storage.rows("SELECT * FROM changes WHERE is_alert=1")[0]
    assert (row["from_version"], row["to_version"], row["review_status"]) == (1, 2, "pending")


def test_parser_failure_keeps_last_good_version_and_flags_stale(settings, storage, fx):
    src = src_of(settings)
    cycle(settings, storage, src, 200, fx("privacy_v1.html"), 0)
    s = cycle(settings, storage, src, 200, fx("privacy_selector_changed.html"), 1)
    assert s.parsed_failed == 1 and s.alerts == 0
    st = storage.state(src.id)
    assert st["last_status"] == "parser_failure" and st["last_success"].startswith("2026-11-01")
    assert st["consecutive_failures"] == 1
    later = T0 + timedelta(days=5)
    f = [x for x in freshness(settings, storage, now=later) if x["source_id"] == src.id][0]
    assert f["stale"] and "STALE" in f["warning"]


def test_possible_truncation_is_not_a_deletion(settings, fx):
    src = src_of(settings)
    full = parse_policy(fx("privacy_v1.html"), src.selectors)
    tiny = parse_policy("<main id='policy-content'><h2>A</h2><p>" + "word " * 20 + "</p></main>", src.selectors)
    r = validate(tiny, 50, prev_chars=full.total_chars)
    assert "possible_truncation" in r.errors


def test_review_workflow(settings, storage, fx):
    src = src_of(settings)
    cycle(settings, storage, src, 200, fx("privacy_v1.html"), 0)
    cycle(settings, storage, src, 200, fx("privacy_retention_edit.html"), 1)
    cid = storage.rows("SELECT id FROM changes WHERE is_alert=1")[0]["id"]
    storage.review(cid, "confirmed", "midhun", "verified on live page")
    r = storage.rows("SELECT review_status, reviewed_by FROM changes WHERE id=?", (cid,))[0]
    assert (r["review_status"], r["reviewed_by"]) == ("confirmed", "midhun")


def test_live_mode_respects_approval_gate(settings):
    assert settings.live_sources() == []      # demo sources are DEMO_ONLY


def test_labelled_change_cases_meet_threshold(settings):
    from ptct.evaluation import run_cases, summarise
    res = run_cases(settings)
    s = summarise(res)
    assert s["cases"] >= 12 and s["false_alerts"] == 0 and s["missed_alerts"] == 0 and s["passed"] == s["cases"]
