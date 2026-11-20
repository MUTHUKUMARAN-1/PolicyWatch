# Report input - Web Scraping & Data Collection role
(Paste into the team report: sections 03, 04, 05, 06 and 08 of the SRS "Final report contents". Replace the bracketed items.)

## 03 Source selection
* Selected public documents: [exact URLs, once approved] - privacy policy and terms of service pages.
* Permission/terms review: [summary of ToS clause + date reviewed]. Robots analysis: [robots.txt path result + date]. Written mentor approval: [date/ref].
* Data dictionary: see `docs/data_dictionary.md`. Collection cadence: once per 24 h (periodic scheduled refresh; **not** real-time push - the sources do not offer streaming).

## 04 Architecture (collection layer)
`config/sources.yaml` -> **Fetcher** (robots check, descriptive User-Agent, timeout, >=10 s interval, exponential backoff, stops on 403/429, no CAPTCHA bypass) -> **Parser** (BeautifulSoup, per-source CSS selectors, heading-based sections, text normalisation) -> **Validator** (schema/sanity gates, truncation guard) -> **Differ** (classification) -> **SQLite storage** (versions, snapshots, changes, runs, freshness state) -> CSV/DB hand-off to the UI team.

## 05 Collection evidence
* Three or more timestamped refresh cycles: `docs/evidence/demo_run/run_log.jsonl` (7 cycles, 2 sources) and `docs/evidence/demo_run/exports/*.csv`.
* Before/after records: `changes.csv` (`before_text`, `after_text`). Raw HTML kept for offline replay in `fixtures/` and `docs/evidence/demo_run/snapshots/`.
* **Replace/add** your live-run logs once the mentor approves a real source (`logs/run_log.jsonl`, `data/exports/`).

## 06 Testing
* 38 automated tests (`pytest -q`): parser field accuracy, change detection, duplicate handling, retry/backoff, 429/403 stop, robots, CAPTCHA-not-bypassed, config validation, CP-5 scenario.
* 17 labelled change cases (`docs/evidence/change_case_results.csv`): 17/17 correct, 0 false change alerts out of 10 negative cases, 0 missed alerts out of 7 positive cases. *These cases are written by the author on synthetic pages, so the figures show the logic is consistent - not that live sites will behave identically. Report any live false alerts honestly.*

## 08 Risks (collection layer)
Source layout change (selector break -> `parser_failure`, stale warning); blocked pages (robots/403/429/CAPTCHA -> stop, switch source/API); inaccurate text extraction (fixtures + manual verification of 10 rows); privacy/fair use (public non-personal text only; store snapshots for analysis, do not republish full pages); retry limits (max 3, then wait for next cycle).
