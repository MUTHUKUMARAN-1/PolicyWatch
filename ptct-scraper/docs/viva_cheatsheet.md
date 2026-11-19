# Viva / live-challenge cheat sheet (Web Scraping & Data Collection)

**Why is the source authorised?** I read the site's terms and robots.txt, recorded the result, and my mentor approved it in writing (CP-1). The code refuses live collection unless `approval_status: APPROVED` (`config.py: live_sources`).

**What happens after HTTP 429?** `fetcher.py` stops immediately (no retry), records `rate_limited` and the `Retry-After` header, keeps the previous version, marks the source stale if needed, and waits for the next scheduled cycle. 403 is handled the same way. Only 5xx/timeouts/connection errors are retried (2 s, 4 s, 8 s).

**Missing listing = removed or parse failure?** A section counts as removed only if the page was fetched (200), parsed and validated and the heading is absent. 404/timeouts -> `fetch_error`; selector break/empty body/>75% text collapse -> `parser_failure`. Neither creates a deletion (see `differ.py`, `validator.py`, tests `test_pipeline.py`).

**A selector changed - how do I fix it?** Run `python -m ptct.cli run --offline` against the saved snapshot, look at `logs/run_log.jsonl` (`selector_issue: body_selector_not_found`), open the snapshot in `data/snapshots/<source>/`, find the new container, update `selectors.body` (a list gives fallbacks) in `config/sources.yaml`, rerun tests. No code change needed.

**Formatting-only edit?** Text is normalised (whitespace, quotes, dashes, spacing before punctuation) and hashed per section; unchanged hash => `format_only` event, no version, no alert.

**Rerun duplicates?** Same content hash => `last_seen` is updated, nothing inserted; identical changes are blocked by the unique `change_key`.

**Is it real-time?** No. Scheduled refresh (e.g. cron once a day). The sources do not provide push/streaming.

**Ethics:** public, non-personal policy text only; descriptive User-Agent with contact; low request rate; no login/CAPTCHA bypass; no republishing of full third-party pages.
