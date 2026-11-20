"""Public entry points of the change detection module."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from .classifier import assess_severity, categorize, describe_change
from .differ import RawChange, diff_documents
from .models import Change, ChangeReport, severity_rank
from .normalize import content_hash, normalize_clause, parse_document


def _change_id(raw: RawChange, document_id: Optional[str]) -> str:
    """Deterministic id: same change on the same document -> same id (safe for DB upserts)."""
    key = "|".join([
        document_id or "",
        raw.change_type,
        raw.scope,
        raw.section_id,
        normalize_clause(raw.old_text or ""),
        normalize_clause(raw.new_text or ""),
    ])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def classify_change(raw: RawChange, document_id: Optional[str] = None) -> Change:
    """Attach category + severity to one raw structural change."""
    heading = raw.section_heading.split(" -> ")[-1]
    categories = categorize([raw.old_text, raw.new_text], heading=heading)
    severity, score, reasons = assess_severity(
        raw.change_type, raw.old_text, raw.new_text, raw.similarity, categories, scope=raw.scope
    )
    return Change(
        change_id=_change_id(raw, document_id),
        change_type=raw.change_type,
        scope=raw.scope,
        severity=severity,
        category=categories[0],
        categories=categories,
        section_id=raw.section_id,
        section_heading=raw.section_heading,
        old_text=raw.old_text,
        new_text=raw.new_text,
        old_position=raw.old_position,
        new_position=raw.new_position,
        similarity=raw.similarity,
        inline_diff=raw.inline_diff,
        reasons=reasons,
        score=score,
        title=describe_change(raw.change_type, raw.scope, raw.old_text, raw.new_text, heading),
    )


def detect_changes(
    old_content: str,
    new_content: str,
    *,
    document_id: Optional[str] = None,
    old_version_id: Optional[str] = None,
    new_version_id: Optional[str] = None,
    content_type: str = "auto",
    include_formatting: bool = True,
    min_severity: str = "none",
) -> ChangeReport:
    """Compare two versions of a policy and return a classified ``ChangeReport``.

    Args:
        old_content: previous scraped version (HTML or plain text).
        new_content: latest scraped version (HTML or plain text).
        document_id: id of the policy in the DB (e.g. "google-privacy"); stored on the report.
        old_version_id / new_version_id: DB ids of the two snapshots; stored on the report.
        content_type: "auto" (default), "html" or "text".
        include_formatting: if False, cosmetic-only edits are dropped from the report.
        min_severity: drop changes below this level ("none", "minor", "moderate", "major").

    Returns:
        ChangeReport. Use ``.to_dict()`` / ``.to_json()`` for storage or APIs,
        ``.to_rows()`` for a flat DB table, ``.summary()`` for notifications.
    """
    old_sections = parse_document(old_content or "", content_type)
    new_sections = parse_document(new_content or "", content_type)
    changes: List[Change] = [classify_change(r, document_id) for r in diff_documents(old_sections, new_sections)]

    if not include_formatting:
        changes = [c for c in changes if c.change_type != "formatting"]
    threshold = severity_rank(min_severity)
    changes = [c for c in changes if severity_rank(c.severity) >= threshold]

    return ChangeReport(
        document_id=document_id,
        old_version_id=old_version_id,
        new_version_id=new_version_id,
        old_hash=content_hash(old_content or ""),
        new_hash=content_hash(new_content or ""),
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        changes=changes,
    )


def has_meaningful_change(old_content: str, new_content: str) -> bool:
    """Cheap check: do the two versions differ beyond cosmetics?

    Uses normalised hashes only, so it is fast enough to run on every scrape.
    """
    return content_hash(old_content or "") != content_hash(new_content or "")
