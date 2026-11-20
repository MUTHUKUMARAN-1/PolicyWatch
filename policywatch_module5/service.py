"""SQLite-backed notification and freshness tracking for PolicyWatch.

This module deliberately does not scrape websites. It consumes successful check
results and detected-change events produced by the existing collection module.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime] = None) -> str:
    return (value or _now()).astimezone(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class FreshnessConfig:
    """Age thresholds. A source becomes stale after stale_after_hours."""
    stale_after_hours: int = 24 * 7
    warning_after_hours: int = 24 * 5

    def __post_init__(self):
        if self.warning_after_hours < 0 or self.stale_after_hours <= 0:
            raise ValueError("Freshness thresholds must be non-negative/positive.")
        if self.warning_after_hours > self.stale_after_hours:
            raise ValueError("warning_after_hours cannot exceed stale_after_hours.")


class NotificationFreshnessService:
    """Service for check timestamps, freshness states and notification history."""

    def __init__(self, database_path: str = "policywatch_module5.db",
                 config: FreshnessConfig = FreshnessConfig()):
        self.database_path = database_path
        self.config = config
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS m5_source_freshness (
                    source_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    last_checked_at TEXT,
                    last_changed_at TEXT,
                    last_status TEXT NOT NULL DEFAULT 'never_checked',
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS m5_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(source_id, notification_type, created_at),
                    FOREIGN KEY(source_id) REFERENCES m5_source_freshness(source_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_m5_notifications_unread
                    ON m5_notifications(is_read, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_m5_freshness_checked
                    ON m5_source_freshness(last_checked_at);
            """)

    def record_check(self, source_id: str, source_name: str,
                     success: bool = True, error: Optional[str] = None,
                     checked_at: Optional[datetime] = None) -> dict[str, Any]:
        """Record a check attempt. Failed checks do not erase the previous success."""
        if not source_id or not source_name:
            raise ValueError("source_id and source_name are required.")
        stamp = _iso(checked_at)
        status = "checked" if success else "check_failed"
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO m5_source_freshness
                    (source_id, source_name, last_checked_at, last_status, last_error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_name=excluded.source_name,
                    last_checked_at=CASE WHEN ? THEN excluded.last_checked_at
                                          ELSE m5_source_freshness.last_checked_at END,
                    last_status=excluded.last_status,
                    last_error=excluded.last_error,
                    updated_at=excluded.updated_at
            """, (source_id, source_name, stamp if success else None, status,
                  None if success else (error or "Unknown collection error"), stamp, int(success)))
            if not success:
                self._add_notification(conn, source_id, source_name, "check_failed",
                    "Policy check failed",
                    f"Could not refresh {source_name}. The previous successful check is retained.",
                    stamp)
        return self.get_freshness(source_id)

    def record_change(self, source_id: str, source_name: str, summary: str,
                      changed_at: Optional[datetime] = None) -> dict[str, Any]:
        """Call this when the existing change-detection module reports a real change."""
        if not source_id or not source_name:
            raise ValueError("source_id and source_name are required.")
        stamp = _iso(changed_at)
        summary = (summary or "A policy change was detected.").strip()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO m5_source_freshness
                    (source_id, source_name, last_changed_at, last_status, updated_at)
                VALUES (?, ?, ?, 'changed', ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_name=excluded.source_name,
                    last_changed_at=excluded.last_changed_at,
                    last_status='changed',
                    updated_at=excluded.updated_at
            """, (source_id, source_name, stamp, stamp))
            self._add_notification(conn, source_id, source_name, "policy_changed",
                f"Policy updated: {source_name}", summary, stamp)
        return self.get_freshness(source_id)

    def _add_notification(self, conn, source_id, source_name, kind, title, message, stamp):
        conn.execute("""
            INSERT INTO m5_notifications
                (source_id, source_name, notification_type, title, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source_id, source_name, kind, title, message, stamp))

    def get_freshness(self, source_id: str, now: Optional[datetime] = None) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM m5_source_freshness WHERE source_id=?", (source_id,)
            ).fetchone()
        if row is None:
            return {"source_id": source_id, "status": "never_checked",
                    "last_checked_at": None, "last_changed_at": None, "age_hours": None}
        result = dict(row)
        if not row["last_checked_at"]:
            result.update(status="never_checked", age_hours=None)
            return result
        checked = datetime.fromisoformat(row["last_checked_at"])
        age = max(0.0, ((_now() if now is None else now).astimezone(timezone.utc) - checked).total_seconds()/3600)
        if age >= self.config.stale_after_hours:
            state = "stale"
        elif age >= self.config.warning_after_hours:
            state = "aging"
        else:
            state = "fresh"
        result.update(status=state, age_hours=round(age, 2))
        return result

    def list_freshness(self, now: Optional[datetime] = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            ids = [r["source_id"] for r in conn.execute(
                "SELECT source_id FROM m5_source_freshness ORDER BY source_name"
            )]
        return [self.get_freshness(source_id, now) for source_id in ids]

    def list_notifications(self, unread_only: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000.")
        query = "SELECT * FROM m5_notifications"
        if unread_only:
            query += " WHERE is_read=0"
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(query, (limit,))]

    def mark_notification_read(self, notification_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE m5_notifications SET is_read=1 WHERE id=?", (notification_id,)
            )
            return cur.rowcount > 0

    def mark_all_read(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("UPDATE m5_notifications SET is_read=1 WHERE is_read=0")
            return cur.rowcount

    def freshness_summary(self) -> dict[str, int]:
        summary = {"total": 0, "fresh": 0, "aging": 0, "stale": 0, "never_checked": 0}
        for item in self.list_freshness():
            summary["total"] += 1
            summary[item["status"]] = summary.get(item["status"], 0) + 1
        return summary
              
