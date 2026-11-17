"""Data shapes produced by the change detection module.

Everything here is a plain dataclass that converts to JSON-safe dicts with
``to_dict()`` so other parts of PolicyWatch (Database, Notifications,
Diff View, Testing) can store or render results without importing any
logic from this package.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# Ordered from least to most significant. "none" is used for cosmetic,
# formatting-only edits (case, quotes, punctuation) that do not change meaning.
SEVERITY_LEVELS = ("none", "minor", "moderate", "major")

CHANGE_TYPES = ("added", "removed", "modified", "moved", "formatting")

SCOPES = ("section", "clause", "heading")


def severity_rank(severity: str) -> int:
    """Return the numeric rank of a severity (none=0 ... major=3)."""
    try:
        return SEVERITY_LEVELS.index(severity)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown severity {severity!r}; expected one of {SEVERITY_LEVELS}") from exc


@dataclass
class DiffSegment:
    """One piece of a word-level inline diff.

    ``op`` is ``"equal"``, ``"insert"`` or ``"delete"``. A diff viewer can
    render inserts in green and deletes in red, in order.
    """

    op: str
    text: str


@dataclass
class Change:
    """A single detected change between two versions of a policy."""

    change_id: str
    change_type: str  # one of CHANGE_TYPES
    scope: str  # one of SCOPES
    severity: str  # one of SEVERITY_LEVELS
    category: str  # primary category, e.g. "data_sharing"
    categories: List[str]  # every category that matched, primary first
    section_id: str
    section_heading: str
    old_text: Optional[str]
    new_text: Optional[str]
    old_position: Optional[int]  # clause index inside the old section
    new_position: Optional[int]  # clause index inside the new section
    similarity: float  # 0.0 - 1.0 word similarity between old and new text
    inline_diff: List[DiffSegment] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)  # why this severity was chosen
    score: int = 0  # raw significance score behind the severity
    title: str = ""  # plain-English one-liner, e.g. "Number changed: 30 -> 365"

    @property
    def is_cosmetic(self) -> bool:
        return self.severity == "none"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["is_cosmetic"] = self.is_cosmetic
        return data


@dataclass
class ChangeReport:
    """Result of comparing an old and a new version of one policy document."""

    document_id: Optional[str]
    old_version_id: Optional[str]
    new_version_id: Optional[str]
    old_hash: str
    new_hash: str
    generated_at: str  # ISO-8601 UTC timestamp
    changes: List[Change] = field(default_factory=list)

    # ---- convenience views -------------------------------------------------

    @property
    def max_severity(self) -> str:
        if not self.changes:
            return "none"
        return max((c.severity for c in self.changes), key=severity_rank)

    @property
    def has_changes(self) -> bool:
        """True if anything at all differs (including cosmetic edits)."""
        return bool(self.changes)

    @property
    def has_significant_changes(self) -> bool:
        """True if at least one change is more than cosmetic."""
        return severity_rank(self.max_severity) > 0

    def filter(self, min_severity: str = "minor", categories: Optional[List[str]] = None) -> List[Change]:
        """Return changes at or above ``min_severity``, optionally limited to categories."""
        threshold = severity_rank(min_severity)
        result = [c for c in self.changes if severity_rank(c.severity) >= threshold]
        if categories:
            wanted = set(categories)
            result = [c for c in result if wanted.intersection(c.categories)]
        return result

    def summary(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {t: 0 for t in CHANGE_TYPES}
        by_severity: Dict[str, int] = {s: 0 for s in SEVERITY_LEVELS}
        by_category: Dict[str, int] = {}
        for c in self.changes:
            by_type[c.change_type] += 1
            by_severity[c.severity] += 1
            by_category[c.category] = by_category.get(c.category, 0) + 1
        return {
            "total_changes": len(self.changes),
            "significant_changes": sum(1 for c in self.changes if not c.is_cosmetic),
            "max_severity": self.max_severity,
            "significance_score": sum(c.score for c in self.changes),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_category": dict(sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))),
            "headline": self.headline(),
        }

    def headline(self) -> str:
        """One-line human summary, suitable for a notification title."""
        if not self.changes:
            return "No changes detected."
        sig = [c for c in self.changes if not c.is_cosmetic]
        if not sig:
            return f"{len(self.changes)} formatting-only change(s); no change in meaning."
        counts = {s: 0 for s in SEVERITY_LEVELS[1:]}
        for c in sig:
            counts[c.severity] += 1
        parts = [f"{n} {s}" for s, n in reversed(list(counts.items())) if n]
        cats: List[str] = []
        for c in sorted(sig, key=lambda c: -severity_rank(c.severity)):
            if c.category not in cats:
                cats.append(c.category)
        return f"{len(sig)} significant change(s) ({', '.join(parts)}) affecting: {', '.join(cats[:4])}."

    # ---- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "old_version_id": self.old_version_id,
            "new_version_id": self.new_version_id,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "generated_at": self.generated_at,
            "summary": self.summary(),
            "changes": [c.to_dict() for c in self.changes],
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_rows(self) -> List[Dict[str, Any]]:
        """Flatten into one dict per change, ready for a ``policy_changes`` DB table.

        List / nested fields are JSON-encoded strings so they fit in TEXT columns.
        """
        rows = []
        for c in self.changes:
            rows.append(
                {
                    "change_id": c.change_id,
                    "document_id": self.document_id,
                    "old_version_id": self.old_version_id,
                    "new_version_id": self.new_version_id,
                    "detected_at": self.generated_at,
                    "title": c.title,
                    "change_type": c.change_type,
                    "scope": c.scope,
                    "severity": c.severity,
                    "category": c.category,
                    "categories": json.dumps(c.categories),
                    "section_id": c.section_id,
                    "section_heading": c.section_heading,
                    "old_text": c.old_text,
                    "new_text": c.new_text,
                    "similarity": c.similarity,
                    "score": c.score,
                    "reasons": json.dumps(c.reasons),
                    "inline_diff": json.dumps([asdict(s) for s in c.inline_diff]),
                }
            )
        return rows

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangeReport":
        """Rebuild a report from ``to_dict()`` output (e.g. loaded from the DB)."""
        changes = []
        for c in data.get("changes", []):
            c = dict(c)
            c.pop("is_cosmetic", None)
            c["inline_diff"] = [DiffSegment(**s) for s in c.get("inline_diff", [])]
            changes.append(Change(**c))
        return cls(
            document_id=data.get("document_id"),
            old_version_id=data.get("old_version_id"),
            new_version_id=data.get("new_version_id"),
            old_hash=data["old_hash"],
            new_hash=data["new_hash"],
            generated_at=data["generated_at"],
            changes=changes,
        )
