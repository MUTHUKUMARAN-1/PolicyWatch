# CP-1 Source approval pack (fill in and submit to mentor)

**Project title:** Privacy Policy & Terms Change Tracker   **Student:** ____ / ID ____ / Team ____  **Mentor:** ____

## Real-world user problem
People accept privacy policies / terms of service that later change silently. The tool detects and shows *what* changed, *when*, with before/after evidence.

## Source alternatives (present 2-3)
| # | Exact public URL | Doc type | Page format (static/JS) | Refresh | Robots.txt path allowed? | ToS allows automated access? | Evidence link/screenshot |
|---|---|---|---|---|---|---|---|
| 1 | | | | daily | | | |
| 2 | | | | daily | | | |
| 3 | | | | daily | | | |

How to check: open `https://<site>/robots.txt` and confirm the policy path is not Disallowed for `User-agent: *` (or the bot name); read the site's Terms of Use for clauses on scraping/automation; if either forbids it, choose another site or an official API (SRS section 4).

## Data-contract fields (6+)
source_id, company, doc_type, original/canonical URL, title, effective_date (source_updated_at), detected_at, section heading, section text hash, before/after text, change category, run_id.

## Crawl limits proposed
User-Agent with contact e-mail; timeout 15 s; >=10 s between requests; <=3 retries with exponential backoff; stop on 403/429; max 10 pages/run; once per day.

## Mentor decision
Approved sources: ______  Blocked/replaced: ______  Written approval ref/date: ______  Initials: ____

> Only after this is signed: set `approval_status: APPROVED` for the approved source(s) in `config/sources.yaml`.
