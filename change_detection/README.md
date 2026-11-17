# Part 6 — Change Detection and Classification

**Owner:** Divyesh Hari · **Package:** `change_detection/` · **Language:** Python 3.9+ · **Dependencies:** none (standard library only)

This module takes two scraped versions of a policy document (old and new, as HTML or plain text). It finds what changed (added, removed, modified or moved clauses and sections) and classifies each change:

- **Type:** `added`, `removed`, `modified`, `moved`, `formatting`
- **Severity:** `none` (cosmetic only) < `minor` < `moderate` < `major`
- **Category:** `data_sharing`, `data_collection`, `cookies_tracking`, `data_retention`, `security`, `user_rights`, `payments`, `legal`, `account_termination`, `children`, `communications`, `policy_updates`, `general`

Whitespace-only edits are dropped entirely. Case, quote style, dash style, bullet style, HTML markup and section renumbering are reported as `formatting` with severity `none`, so they never trigger alerts.

## Folder layout

```
change_detection/
├── __init__.py        public API (import from here)
├── api.py             detect_changes(), has_meaningful_change(), classify_change()
├── models.py          Change, ChangeReport, DiffSegment: the output data shapes
├── normalize.py       HTML -> text, sections/clauses, normalisation, content_hash()
├── differ.py          section alignment + clause-level diff + inline word diff
├── classifier.py      category keywords + severity scoring rules
├── __main__.py        command line interface
├── samples/           example old/new policies (HTML and text)
└── tests/             unit tests (41 tests)
```

## Quick start

```bash
# from the repo root (the folder that contains change_detection/)
python -m change_detection change_detection/samples/privacy_v1.html change_detection/samples/privacy_v2.html
python -m change_detection change_detection/samples/terms_v1.txt change_detection/samples/terms_v2.txt --json
```

CLI options: `--json` prints the full report, `--min-severity minor|moderate|major` filters, `--no-formatting` hides cosmetic edits, and `--document-id ID` sets the document id.

## Demo website

```bash
python -m change_detection.demo_server        # then open http://localhost:8765
```

This is a local page (standard library only) where you paste an old and a new version, or load a bundled sample, and see the classified changes. Each change shows a colour-coded inline diff, severity filters and the reasons for its severity. A **Show JSON** button shows the raw report. The same server exposes `POST /api/compare` (`{"old": ..., "new": ...}` → report JSON), which other parts can call over HTTP. This is only a demo tool for Part 6. The real Diff View is Part 4.

## Running the tests

```bash
python -m unittest discover -s change_detection/tests -t . -v
# or, if pytest is installed:
python -m pytest change_detection/tests -v
```

## Python API

```python
from change_detection import detect_changes, has_meaningful_change, content_hash

report = detect_changes(
    old_content,                 # str: previous snapshot (HTML or text)
    new_content,                 # str: latest snapshot (HTML or text)
    document_id="exampleapp-privacy",   # optional, copied onto the report
    old_version_id="17",                # optional DB id of old snapshot
    new_version_id="18",                # optional DB id of new snapshot
    content_type="auto",                # "auto" | "html" | "text"
    include_formatting=True,            # False drops cosmetic-only changes
    min_severity="none",                # drop changes below this level
)

report.has_changes              # anything differs (incl. cosmetic)
report.has_significant_changes  # anything beyond cosmetic
report.max_severity             # "none" | "minor" | "moderate" | "major"
report.summary()                # counts + one-line headline
report.filter(min_severity="major", categories=["payments", "data_sharing"])
report.to_dict() / report.to_json()   # full structured output
report.to_rows()                # one flat dict per change, for a SQL table
ChangeReport.from_dict(d)       # rebuild a stored report
```

### Output shape (`report.to_dict()`)

```json
{
  "document_id": "exampleapp-privacy",
  "old_version_id": "v1",
  "new_version_id": "v2",
  "old_hash": "sha256 of normalised old text",
  "new_hash": "sha256 of normalised new text",
  "generated_at": "2026-11-17T10:30:00+00:00",
  "summary": {
    "total_changes": 10,
    "significant_changes": 8,
    "max_severity": "major",
    "significance_score": 37,
    "by_type":     {"added": 2, "removed": 2, "modified": 4, "moved": 0, "formatting": 2},
    "by_severity": {"none": 2, "minor": 1, "moderate": 0, "major": 7},
    "by_category": {"payments": 2, "data_sharing": 1, "...": 1},
    "headline": "8 significant change(s) (7 major, 1 minor) affecting: data_collection, data_sharing, ..."
  },
  "changes": [
    {
      "change_id": "a1b2c3d4e5f60718",
      "change_type": "modified",
      "scope": "clause",
      "severity": "major",
      "category": "data_sharing",
      "categories": ["data_sharing", "data_collection"],
      "section_id": "how-we-share-your-information",
      "section_heading": "2. How We Share Your Information",
      "old_text": "We will not sell your personal data to third parties.",
      "new_text": "We may sell your personal data to advertising partners.",
      "old_position": 0,
      "new_position": 0,
      "similarity": 0.632,
      "inline_diff": [
        {"op": "equal",  "text": "We"},
        {"op": "delete", "text": "will not"},
        {"op": "insert", "text": "may"},
        {"op": "equal",  "text": "sell your personal data to"},
        {"op": "delete", "text": "third parties."},
        {"op": "insert", "text": "advertising partners."}
      ],
      "reasons": [
        "Negation changed (removed 'not'); meaning may be reversed.",
        "Obligation/permission wording changed (will -> may).",
        "..."
      ],
      "score": 11,
      "title": "Meaning reversed: 'will not' became 'may'",
      "is_cosmetic": false
    }
  ]
}
```

Field notes:

- `scope` is `section` (a whole section was added or removed), `clause` (one sentence or list item) or `heading` (a section was renamed).
- `old_text` is `null` for additions and `new_text` is `null` for removals.
- `change_id` is deterministic. The same change on the same document always gets the same id, so it is safe to use as a primary key or for upserts.
- `reasons` explains which rules set the severity, which is useful for the report and the UI.
- `title` is a plain-English one-liner for non-experts (UI cards and notification lines), such as "Number changed: 30 -> 365" or "User protection removed (opt out)".

## How other parts plug in

| Part | What to call | What you get |
|------|--------------|--------------|
| **1 Scraping** | Nothing; just keep the raw HTML/text of each snapshot. | |
| **2 Database** | `report.to_rows()` → insert into a `policy_changes` table; optionally store `report.to_json()` per version pair. Store `content_hash(text)` on each snapshot. | Flat rows with only str/int/float/None values (lists are JSON strings). |
| **4 Search / Filter / Diff View** | Render `changes[*].inline_diff` (green = `insert`, red = `delete`). Filter on `severity`, `category`, `change_type`, `section_id`. | Ordered segments per change. |
| **5 Notifications / Freshness** | On each scrape: `has_meaningful_change(old, new)` (cheap hash check). If true: `detect_changes(...)`, then alert when `report.has_significant_changes`, using `report.summary()["headline"]` as the message and `report.filter(min_severity="moderate")` for the details. | Boolean + headline + filtered list. |
| **7 Testing / Report** | `python -m unittest discover -s change_detection/tests -t . -v`; sample inputs are in `samples/`. | Test results and example outputs. |

Suggested table (SQLite/MySQL, adjust types as needed):

```sql
CREATE TABLE policy_changes (
  change_id       VARCHAR(16) PRIMARY KEY,
  document_id     VARCHAR(100),
  old_version_id  VARCHAR(50),
  new_version_id  VARCHAR(50),
  detected_at     VARCHAR(30),
  change_type     VARCHAR(12),   -- added | removed | modified | moved | formatting
  scope           VARCHAR(10),   -- section | clause | heading
  severity        VARCHAR(10),   -- none | minor | moderate | major
  category        VARCHAR(30),
  categories      TEXT,          -- JSON list
  section_id      VARCHAR(120),
  section_heading TEXT,
  old_text        TEXT,
  new_text        TEXT,
  similarity      REAL,
  score           INTEGER,
  reasons         TEXT,          -- JSON list
  inline_diff     TEXT           -- JSON list of {op, text}
);
```

## How it works

1. **Parse** (`normalize.py`): HTML is stripped of scripts, styles, nav, footer and forms. Headings (`<h1>`–`<h6>`, numbered lines, ALL CAPS lines, short Title Case lines) start new sections. Paragraphs are split into sentences and list items, which are the *clauses*.
2. **Align sections** (`differ.py`): sections are matched by a slug of the heading with numbering removed, so renumbering doesn't break matching. Renamed sections are matched by fuzzy heading similarity (≥ 0.75) or body similarity (≥ 0.6).
3. **Diff clauses**: `difflib.SequenceMatcher` runs over the *normalised* clauses. Replaced clauses are paired by word similarity (≥ 0.45, or ≥ 0.3 for a one-to-one replacement) into `modified` changes, and the rest become `added` or `removed`. A clause removed in one place and added verbatim elsewhere becomes `moved`.
4. **Classify** (`classifier.py`):
   - **Category:** keyword matching on old and new text, with heading keywords counted double.
   - **Severity:** a points score, described below.

| Rule | Points |
|------|--------|
| Wording changed 20–50% / > 50% | +1 / +2 |
| Clause added/removed (+1 if whole section, +1 if > 30 words) | +1 |
| Sensitive category (sharing, collection, retention, security, rights, payments, legal, children, termination, cookies) | +1 |
| Negation flipped (not, never, without…) | +3 |
| Modal changed (may / will / must / shall…) | +2 |
| Number, price, % or time period changed | +3 |
| Introduces risky terms (sell, third parties, arbitration, without notice, non-refundable…) | +2 |
| Removes protective terms (consent, opt out, notify, refund, delete…) | +2 |

Total 0–1 → `minor`, 2–3 → `moderate`, ≥ 4 → `major`. Formatting-only changes are always `none`, moves are `minor`, and edits that only change the "Last updated" or "Effective date" line are `minor`.

### Known limitations

- The rules are keyword-based, not NLP. They can miss reworded meaning changes that use none of the keywords, and they can over-flag a harmless edit in a sensitive section.
- Sentence splitting is regex-based, so unusual abbreviations may split a sentence in two.
- Moves of whole sections are reported as a section removal plus an addition.
