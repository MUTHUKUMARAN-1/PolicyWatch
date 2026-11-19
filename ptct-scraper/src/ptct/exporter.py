"""CSV exports for evidence / hand-over to the UI & analysis teammates."""
from __future__ import annotations

import csv
from pathlib import Path

from .storage import Storage

QUERIES = {
    "versions.csv": "SELECT source_id, version_no, first_seen, last_seen, content_hash, title, effective_date, snapshot_id FROM versions ORDER BY source_id, version_no",
    "changes.csv": "SELECT id, run_id, source_id, url, detected_at, category, is_alert, section, before_text, after_text, from_version, to_version, review_status, reviewed_by, review_note FROM changes ORDER BY id",
    "runs.csv": "SELECT * FROM runs ORDER BY started_at",
    "snapshots.csv": "SELECT id, run_id, source_id, url, fetched_at, fetch_status, http_code, raw_hash, raw_path, parse_status, error FROM snapshots ORDER BY id",
    "source_state.csv": "SELECT * FROM source_state ORDER BY source_id",
}


def export_all(storage: Storage, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, sql in QUERIES.items():
        rows = storage.rows(sql)
        path = out / name
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if rows:
                w.writerow(rows[0].keys())
                for r in rows:
                    w.writerow(list(r))
            else:
                w.writerow([c.split()[-1] for c in sql.split("FROM")[0].replace("SELECT", "").split(",")])
        written.append(path)
    return written
