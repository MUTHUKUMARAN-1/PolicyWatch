"""Change classification between two stored versions.

Alert categories (real content changes):
  section_added, section_removed, section_edited, section_renamed, date_changed, title_changed
Non-alert events (never counted as policy changes):
  format_only, fetch_error, parser_failure, baseline
A missing page (HTTP 404) or a parser failure is NEVER treated as a deletion.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .parser import ParsedDoc

ALERT_CATEGORIES = {"section_added", "section_removed", "section_edited", "section_renamed",
                    "date_changed", "title_changed"}


@dataclass
class Change:
    category: str
    section: str | None
    before: str | None
    after: str | None

    @property
    def is_alert(self) -> bool:
        return self.category in ALERT_CATEGORIES


def _sentences(t: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]


def _snippet(old: str, new: str, limit: int = 600) -> tuple[str, str]:
    a, b = _sentences(old), _sentences(new)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    rem, add = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            rem += a[i1:i2]
        if tag in ("replace", "insert"):
            add += b[j1:j2]
    return " ".join(rem)[:limit], " ".join(add)[:limit]


def diff_versions(old: dict, new: ParsedDoc) -> list[Change]:
    out: list[Change] = []
    if (old.get("title") or None) != (new.title or None) and (old.get("title") and new.title):
        out.append(Change("title_changed", None, old["title"], new.title))
    old_date = old.get("effective_date") or old.get("effective_date_raw")
    new_date = new.effective_date or new.effective_date_raw
    if old_date and new_date and old_date != new_date:
        out.append(Change("date_changed", None, old_date, new_date))

    old_secs = {s["heading"]: s for s in old["sections"]}
    new_secs = {s.heading: s for s in new.sections}
    removed = [h for h in old_secs if h not in new_secs]
    added = [h for h in new_secs if h not in old_secs]

    # a heading rename with identical body text is a rename, not remove+add
    for r in list(removed):
        for a in list(added):
            if old_secs[r]["hash"] == new_secs[a].hash:
                out.append(Change("section_renamed", f"{r} -> {a}", r, a))
                removed.remove(r)
                added.remove(a)
                break

    for h in removed:
        out.append(Change("section_removed", h, old_secs[h]["text"][:600], None))
    for h in added:
        out.append(Change("section_added", h, None, new_secs[h].text[:600]))
    for h, s in new_secs.items():
        if h in old_secs and old_secs[h]["hash"] != s.hash:
            before, after = _snippet(old_secs[h]["text"], s.text)
            out.append(Change("section_edited", h, before, after))
    return out
