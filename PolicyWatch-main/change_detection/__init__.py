"""PolicyWatch - Part 6: Change Detection and Classification.

Quick use::

    from change_detection import detect_changes

    report = detect_changes(old_html, new_html, document_id="example-privacy")
    report.summary()      # counts + headline for notifications
    report.to_dict()      # JSON-safe, for the DB / diff view
    report.to_rows()      # one flat dict per change, for a SQL table
"""

from .api import classify_change, detect_changes, has_meaningful_change
from .models import CHANGE_TYPES, SEVERITY_LEVELS, Change, ChangeReport, DiffSegment, severity_rank
from .normalize import content_hash, parse_document

__all__ = [
    "detect_changes",
    "has_meaningful_change",
    "classify_change",
    "content_hash",
    "parse_document",
    "Change",
    "ChangeReport",
    "DiffSegment",
    "SEVERITY_LEVELS",
    "CHANGE_TYPES",
    "severity_rank",
]

__version__ = "1.0.0"
