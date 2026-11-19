"""Schema / sanity validation of a parsed document (FR-02)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .parser import ParsedDoc


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(doc: ParsedDoc, min_body_chars: int = 200, prev_chars: int | None = None) -> ValidationResult:
    r = ValidationResult(warnings=list(doc.warnings))
    if not doc.sections:
        r.errors.append("no_sections")
    if doc.total_chars < min_body_chars:
        r.errors.append("suspiciously_short_body")
    if prev_chars and doc.total_chars < 0.25 * prev_chars:
        # A sudden collapse is far more likely a broken parse/blank page than a real rewrite.
        r.errors.append("possible_truncation")
    if doc.effective_date_raw and not doc.effective_date:
        r.warnings.append("effective_date_unparsed")
    return r
