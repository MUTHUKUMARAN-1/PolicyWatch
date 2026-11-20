[README.md](https://github.com/user-attachments/files/35135122/README.md)
# Privacy Policy & Terms Change Tracker - Web Scraping & Data Collection module

Cybernaut *Web Scraping Project SRS 13* (student-chosen title). This repository holds the **web scraping and data collection** part of the team project: it fetches public privacy-policy / terms-of-service pages, extracts structured sections, stores every version with timestamps, and classifies what changed - while handling failing sites safely.

> **Status of live sources:** no real website is enabled yet. SRS section 3 requires written mentor approval *before* live collection, so the shipped config contains two **synthetic "Acme" demo sources** (offline fixtures) and a commented template for real ones. The live mode refuses to run until a source is marked `APPROVED`.

## Requirement coverage
| SRS | Where |
|---|---|
| FR-01 config (URLs, refresh, field map, crawl limits) | `config/sources.yaml`, `src/ptct/config.py` |
| FR-02 extract + validate fields, source links, timestamps | `parser.py`, `validator.py`, `snapshots` table |
| FR-03 first_seen/last_seen history, new/updated/duplicate | `storage.py`, `runner.py`, `differ.py` |
| FR-04 freshness / stale warning / attribution | `runner.freshness`, `ptct.cli status`, `url` kept on every row |
| FR-05 selector change, missing values, HTTP errors, 429, zero results | `fetcher.py`, `parser.py` (`ParserError`), `validator.py` |
| FR-06 offline tests from saved pages + run commands | `fixtures/`, `tests/`, commands below |
| Sec. 6 low-impact requests, permission gate, observability | `fetcher.py` (UA, timeout, interval, backoff, robots), `logs/run_log.jsonl` |
| Sec. 9 >=12 labelled change cases, false alerts, 3 refresh cycles | `evaluation.py`, `docs/evidence/` |

## Setup
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt && pip install -e .
```

## Run commands
```bash
pytest -q                                   # 38 tests, fully offline
python scripts/evaluate_change_cases.py     # 17 labelled change cases -> docs/evidence/change_case_results.csv
python -m ptct.cli validate-config
python -m ptct.cli demo                     # 7 scripted refresh cycles (change, duplicate, 404, restore, format-only, selector break)
python -m ptct.cli run --offline            # one cycle from the fixture files
python -m ptct.cli status                   # last attempted vs last successful + stale warnings
python -m ptct.cli export                   # CSVs in data/exports/ for the UI / analysis teammates
python -m ptct.cli review --id 3 --status confirmed --by <name> --note "checked on site"
python -m ptct.cli run --live               # ONLY after mentor approval + real contact e-mail in config
```
Schedule live refreshes with cron, e.g. `0 9 * * * cd /path/repo && .venv/bin/python -m ptct.cli run --live`.

## Going live (checklist)
1. Fill `docs/source_approval_checklist.md` (terms + robots review) and get written mentor approval.
2. In `config/sources.yaml` add the source, its CSS selectors, set your contact e-mail in `user_agent`, set `approval_status: APPROVED`.
3. Save a real HTML snapshot into `fixtures/` and add a parser test for it.
4. Run `python -m ptct.cli run --live` three times on different days (or simulate with saved pages) and keep `logs/run_log.jsonl` + `data/exports/` as evidence.

## Hand-off to teammates
The UI/analysis roles read `data/ptct.db` (or the CSV exports): table `changes` (alerts with before/after text, `review_status`), `versions` (full history), `source_state` (freshness). Field meanings: `docs/data_dictionary.md`.

## Honest limitations
* Offline evidence uses synthetic fixtures; live-site results must be added after approval.
* Parsing is CSS-selector based; JavaScript-rendered pages need an approved API or saved HTML (no headless-browser/CAPTCHA bypass is implemented on purpose).
* "Real-time" means scheduled periodic refresh only.
* Text diff is sentence-level; semantic/legal impact scoring belongs to the analysis role.

## Individual contribution & originality
Fill in before submission: _Name / ID / role: web scraping & data collection_. All code in this repo was reviewed and is explainable by the author; sources are cited in the report.
