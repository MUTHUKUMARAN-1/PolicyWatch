"""SQLite storage: versioned, idempotent, with duplicate suppression (FR-03)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, mode TEXT,
  sources_attempted INT DEFAULT 0, parsed_ok INT DEFAULT 0, parsed_failed INT DEFAULT 0,
  fetch_failed INT DEFAULT 0, new_versions INT DEFAULT 0, alerts INT DEFAULT 0, duplicates INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS snapshots(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, source_id TEXT, url TEXT, fetched_at TEXT,
  fetch_status TEXT, http_code INT, raw_hash TEXT, raw_path TEXT, parse_status TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, version_no INT, first_seen TEXT, last_seen TEXT,
  content_hash TEXT, last_raw_hash TEXT, title TEXT, effective_date TEXT, doc_json TEXT, snapshot_id INT,
  UNIQUE(source_id, version_no));
CREATE TABLE IF NOT EXISTS changes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, change_key TEXT UNIQUE, run_id TEXT, source_id TEXT, url TEXT,
  detected_at TEXT, category TEXT, is_alert INT, section TEXT, before_text TEXT, after_text TEXT,
  from_version INT, to_version INT, review_status TEXT DEFAULT 'pending', reviewed_by TEXT, review_note TEXT);
CREATE TABLE IF NOT EXISTS source_state(
  source_id TEXT PRIMARY KEY, last_attempted TEXT, last_success TEXT, last_status TEXT,
  consecutive_failures INT DEFAULT 0, last_error TEXT);
"""


class Storage:
    def __init__(self, db_path: str | Path, snapshot_dir: str | Path):
        self.db_path = str(db_path)
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- runs
    def start_run(self, run_id: str, started_at: str, mode: str) -> None:
        self.db.execute("INSERT INTO runs(run_id, started_at, mode) VALUES(?,?,?)", (run_id, started_at, mode))
        self.db.commit()

    def finish_run(self, run_id: str, finished_at: str, c: dict) -> None:
        self.db.execute(
            "UPDATE runs SET finished_at=?, sources_attempted=?, parsed_ok=?, parsed_failed=?, fetch_failed=?,"
            " new_versions=?, alerts=?, duplicates=? WHERE run_id=?",
            (finished_at, c["attempted"], c["parsed_ok"], c["parsed_failed"], c["fetch_failed"],
             c["new_versions"], c["alerts"], c["duplicates"], run_id))
        self.db.commit()

    # ---- snapshots (raw HTML kept on disk for offline replay)
    def save_raw(self, source_id: str, fetched_at: str, html: str) -> tuple[str, str]:
        raw_hash = hashlib.sha256(html.encode()).hexdigest()
        d = self.snapshot_dir / source_id
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{fetched_at.replace(':', '')}_{raw_hash[:8]}.html"
        path.write_text(html, encoding="utf-8")
        return raw_hash, str(path)

    def add_snapshot(self, **kw) -> int:
        cur = self.db.execute(
            "INSERT INTO snapshots(run_id, source_id, url, fetched_at, fetch_status, http_code, raw_hash,"
            " raw_path, parse_status, error) VALUES(:run_id,:source_id,:url,:fetched_at,:fetch_status,"
            ":http_code,:raw_hash,:raw_path,:parse_status,:error)",
            {"raw_hash": None, "raw_path": None, "parse_status": None, "error": None, "http_code": None, **kw})
        self.db.commit()
        return cur.lastrowid

    # ---- versions
    def latest_version(self, source_id: str):
        return self.db.execute(
            "SELECT * FROM versions WHERE source_id=? ORDER BY version_no DESC LIMIT 1", (source_id,)).fetchone()

    def add_version(self, source_id: str, version_no: int, seen_at: str, doc, raw_hash: str, snapshot_id: int) -> None:
        self.db.execute(
            "INSERT INTO versions(source_id, version_no, first_seen, last_seen, content_hash, last_raw_hash,"
            " title, effective_date, doc_json, snapshot_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (source_id, version_no, seen_at, seen_at, doc.content_hash, raw_hash, doc.title,
             doc.effective_date or doc.effective_date_raw, json.dumps(doc.to_dict(), ensure_ascii=False), snapshot_id))
        self.db.commit()

    def touch_version(self, version_id: int, seen_at: str, raw_hash: str) -> None:
        self.db.execute("UPDATE versions SET last_seen=?, last_raw_hash=? WHERE id=?", (seen_at, raw_hash, version_id))
        self.db.commit()

    # ---- changes
    def add_change(self, *, run_id, source_id, url, detected_at, category, is_alert, section=None,
                   before=None, after=None, from_version=None, to_version=None, key_extra: str = "") -> bool:
        """Insert a change; returns False if an identical change was already stored (duplicate suppression)."""
        key = hashlib.sha256("|".join(map(str, [source_id, category, section, from_version, to_version,
                                                hashlib.sha256((before or "").encode()).hexdigest()[:12],
                                                hashlib.sha256((after or "").encode()).hexdigest()[:12],
                                                key_extra])).encode()).hexdigest()
        cur = self.db.execute(
            "INSERT OR IGNORE INTO changes(change_key, run_id, source_id, url, detected_at, category, is_alert,"
            " section, before_text, after_text, from_version, to_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, run_id, source_id, url, detected_at, category, int(is_alert), section, before, after,
             from_version, to_version))
        self.db.commit()
        return cur.rowcount == 1

    def review(self, change_id: int, status: str, by: str, note: str = "") -> None:
        if status not in ("confirmed", "dismissed", "pending"):
            raise ValueError("status must be confirmed | dismissed | pending")
        self.db.execute("UPDATE changes SET review_status=?, reviewed_by=?, review_note=? WHERE id=?",
                        (status, by, note, change_id))
        self.db.commit()

    # ---- source state / freshness
    def update_state(self, source_id: str, attempted_at: str, success: bool, status: str, error: str | None) -> None:
        row = self.db.execute("SELECT * FROM source_state WHERE source_id=?", (source_id,)).fetchone()
        if row is None:
            self.db.execute("INSERT INTO source_state(source_id) VALUES(?)", (source_id,))
            row = self.db.execute("SELECT * FROM source_state WHERE source_id=?", (source_id,)).fetchone()
        fails = 0 if success else row["consecutive_failures"] + 1
        self.db.execute(
            "UPDATE source_state SET last_attempted=?, last_success=COALESCE(?, last_success), last_status=?,"
            " consecutive_failures=?, last_error=? WHERE source_id=?",
            (attempted_at, attempted_at if success else None, status, fails, error, source_id))
        self.db.commit()

    def state(self, source_id: str):
        return self.db.execute("SELECT * FROM source_state WHERE source_id=?", (source_id,)).fetchone()

    def rows(self, sql: str, args=()) -> list[sqlite3.Row]:
        return self.db.execute(sql, args).fetchall()

    def close(self) -> None:
        self.db.close()
