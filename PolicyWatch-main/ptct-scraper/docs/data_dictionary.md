# Data dictionary

Database: `data/ptct.db` (SQLite). CSV exports: `python -m ptct.cli export` -> `data/exports/`.

## versions  (one row per distinct policy/terms version per source)
| field | type | meaning |
|---|---|---|
| source_id | text | id from `config/sources.yaml` |
| version_no | int | 1, 2, 3 ... increments only when *content* changes |
| first_seen / last_seen | UTC ISO | first and latest refresh that saw this version (FR-03) |
| content_hash | sha256 | hash of title + effective date + normalised section texts |
| title | text/null | document title (null + warning if selector finds nothing - never invented) |
| effective_date | ISO date or raw text/null | "last updated / effective" date from the page |
| doc_json | json | full parsed document: sections `[{heading, text, hash}]` |
| snapshot_id | int | raw snapshot this version was created from |

## changes  (what the UI / analysis teammates consume)
| field | meaning |
|---|---|
| category | `section_added`, `section_removed`, `section_edited`, `section_renamed`, `date_changed`, `title_changed` (**alerts**) / `format_only`, `fetch_error`, `parser_failure`, `baseline` (**events, not alerts**) |
| is_alert | 1 for real content changes, 0 for events |
| section | heading the change applies to |
| before_text / after_text | before/after evidence (changed sentences only, <=600 chars) |
| from_version / to_version | version numbers on either side of the change |
| review_status | `pending` -> `confirmed` / `dismissed` (manual verification pathway) |
| change_key | unique hash - identical changes are suppressed (duplicate suppression) |

## snapshots  (every fetch attempt, successful or not)
run_id, source_id, url, fetched_at, fetch_status (`ok`, `http_error`, `forbidden`, `rate_limited`, `blocked_robots`, `blocked_challenge`, `timeout`, `network_error`), http_code, raw_hash, raw_path (saved HTML for offline replay), parse_status, error.

## runs  (one row per refresh cycle)
run_id, started_at, finished_at, mode (`live`/`offline`), sources_attempted, parsed_ok, parsed_failed, fetch_failed, new_versions, alerts, duplicates.

## source_state  (freshness)
last_attempted, last_success, last_status, consecutive_failures, last_error. A source is **stale** when its last success is older than 2x its `refresh_hours`.

## Classification rules
* A **404/410/timeout/429/403** is a `fetch_error` - the previous version is kept and **never** treated as deletion.
* A page that loads but cannot be parsed (selector renamed, empty body, >75% text collapse) is a `parser_failure` - quarantined, last good version kept, source marked stale.
* Whitespace, markup, class-name, typographic-quote and nav/cookie-banner changes are `format_only` - no version, no alert.
* A section is `section_removed` only when the page parsed successfully and the heading is truly absent.
