"""Structural diff of two parsed policy documents.

1. Align sections between versions (by heading id, then fuzzy heading /
   content similarity, so renamed or renumbered sections still match).
2. Inside each matched pair, align clauses with difflib on their
   *normalised* text, so cosmetic edits are not reported as rewrites.
3. Pair up replaced clauses by similarity into "modified" changes; leftover
   clauses become "added" / "removed".
4. Clauses that were removed in one place and added verbatim elsewhere are
   merged into a single "moved" change.

Produces ``RawChange`` records; classification happens in ``api.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from .models import DiffSegment
from .normalize import Section, collapse_ws, normalize_clause, slugify, words

MODIFIED_THRESHOLD = 0.45  # min word similarity for a replaced clause to count as "modified"
ONE_TO_ONE_THRESHOLD = 0.3  # same, when exactly one clause replaced exactly one clause
SECTION_HEADING_THRESHOLD = 0.75
SECTION_BODY_THRESHOLD = 0.6


@dataclass
class RawChange:
    change_type: str
    scope: str
    section_id: str
    section_heading: str
    old_text: Optional[str]
    new_text: Optional[str]
    old_position: Optional[int]
    new_position: Optional[int]
    similarity: float
    inline_diff: List[DiffSegment] = field(default_factory=list)


def similarity(a: str, b: str) -> float:
    """Word-level similarity ratio in [0, 1] of two texts, ignoring cosmetics."""
    wa, wb = words(a), words(b)
    if not wa and not wb:
        return 1.0
    return SequenceMatcher(None, wa, wb, autojunk=False).ratio()


def inline_diff(old: str, new: str) -> List[DiffSegment]:
    """Word-level diff segments for rendering (raw words, compared case-insensitively)."""
    old_tokens, new_tokens = old.split(), new.split()
    key = lambda toks: [normalize_clause(t) for t in toks]  # noqa: E731
    sm = SequenceMatcher(None, key(old_tokens), key(new_tokens), autojunk=False)
    segs: List[DiffSegment] = []

    def add(op: str, toks: List[str]) -> None:
        if not toks:
            return
        text = " ".join(toks)
        if segs and segs[-1].op == op:
            segs[-1].text += " " + text
        else:
            segs.append(DiffSegment(op, text))

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            add("equal", new_tokens[j1:j2])
        else:
            add("delete", old_tokens[i1:i2])
            add("insert", new_tokens[j1:j2])
    return segs


# --------------------------------------------------------------------------
# Section alignment
# --------------------------------------------------------------------------

def align_sections(old: List[Section], new: List[Section]) -> List[Tuple[Optional[Section], Optional[Section]]]:
    """Return (old, new) pairs; one side is None for added/removed sections.

    Output follows the order of the new document, with removed sections
    placed after the section that preceded them in the old document.
    """
    pairs: dict = {}  # new index -> old index
    used_old = set()
    old_by_id = {s.section_id: i for i, s in enumerate(old)}
    for j, s in enumerate(new):
        i = old_by_id.get(s.section_id)
        if i is not None and i not in used_old:
            pairs[j] = i
            used_old.add(i)

    # Fuzzy-match leftovers (renamed / reworded headings).
    candidates = []
    for j, ns in enumerate(new):
        if j in pairs:
            continue
        for i, os_ in enumerate(old):
            if i in used_old:
                continue
            h = SequenceMatcher(None, normalize_clause(os_.heading), normalize_clause(ns.heading)).ratio()
            b = similarity(os_.text, ns.text)
            if h >= SECTION_HEADING_THRESHOLD or b >= SECTION_BODY_THRESHOLD:
                candidates.append((max(h, b), j, i))
    for _, j, i in sorted(candidates, reverse=True):
        if j not in pairs and i not in used_old:
            pairs[j] = i
            used_old.add(i)

    result: List[Tuple[Optional[Section], Optional[Section]]] = []
    removed = [i for i in range(len(old)) if i not in used_old]
    emitted_removed = set()

    def emit_removed_before(limit: int) -> None:
        for i in removed:
            if i < limit and i not in emitted_removed:
                result.append((old[i], None))
                emitted_removed.add(i)

    for j, ns in enumerate(new):
        if j in pairs:
            emit_removed_before(pairs[j])
            result.append((old[pairs[j]], ns))
        else:
            result.append((None, ns))
    emit_removed_before(len(old))
    return result


# --------------------------------------------------------------------------
# Clause diff
# --------------------------------------------------------------------------

def _pair_block(old_cl: List[Tuple[int, str]], new_cl: List[Tuple[int, str]]):
    """Greedily pair clauses of a replace block by similarity, preserving order."""
    # A lone clause replaced by a lone clause is very likely a rewrite of it,
    # so accept a lower similarity in that case.
    threshold = ONE_TO_ONE_THRESHOLD if len(old_cl) == len(new_cl) == 1 else MODIFIED_THRESHOLD
    scored = []
    for a, (_, o) in enumerate(old_cl):
        for b, (_, n) in enumerate(new_cl):
            s = similarity(o, n)
            if s >= threshold:
                scored.append((s, a, b))
    pairs = {}
    for s, a, b in sorted(scored, reverse=True):
        if a in pairs or b in pairs.values():
            continue
        # keep pairs non-crossing so the diff reads top-to-bottom
        if any((a < a2) != (b < b2) for a2, b2 in pairs.items()):
            continue
        pairs[a] = b
    return pairs


def diff_sections(old: Optional[Section], new: Optional[Section]) -> List[RawChange]:
    if old is None and new is None:
        return []
    if old is None:
        return [RawChange("added", "section", new.section_id, new.heading, None,
                          _section_body(new), None, None, 0.0)]
    if new is None:
        return [RawChange("removed", "section", old.section_id, old.heading,
                          _section_body(old), None, None, None, 0.0)]

    sid, heading = new.section_id, new.heading or old.heading
    changes: List[RawChange] = []

    if slugify(old.heading) != slugify(new.heading):
        changes.append(RawChange("modified", "heading", sid, heading, old.heading, new.heading, None, None,
                                 round(similarity(old.heading, new.heading), 3),
                                 inline_diff(old.heading, new.heading)))
    elif collapse_ws(old.heading) != collapse_ws(new.heading):
        # Same words, different numbering/case/punctuation -> cosmetic.
        changes.append(RawChange("formatting", "heading", sid, heading, old.heading, new.heading, None, None,
                                 1.0, inline_diff(old.heading, new.heading)))

    ok = [normalize_clause(c) for c in old.clauses]
    nk = [normalize_clause(c) for c in new.clauses]
    sm = SequenceMatcher(None, ok, nk, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                o, n = old.clauses[i], new.clauses[j]
                if collapse_ws(o) != collapse_ws(n):
                    changes.append(RawChange("formatting", "clause", sid, heading, o, n, i, j, 1.0, inline_diff(o, n)))
            continue
        old_block = [(i, old.clauses[i]) for i in range(i1, i2)]
        new_block = [(j, new.clauses[j]) for j in range(j1, j2)]
        pairs = _pair_block(old_block, new_block)
        paired_new = set(pairs.values())
        # Walk in new-document order, slotting removed clauses where they were.
        a = 0
        for b, (j, n) in enumerate(new_block):
            match = next((a2 for a2, b2 in pairs.items() if b2 == b), None)
            if match is not None:
                while a < match:
                    if a not in pairs:
                        i, o = old_block[a]
                        changes.append(RawChange("removed", "clause", sid, heading, o, None, i, None, 0.0))
                    a += 1
                i, o = old_block[match]
                changes.append(RawChange("modified", "clause", sid, heading, o, n, i, j,
                                         round(similarity(o, n), 3), inline_diff(o, n)))
                a = match + 1
            elif b not in paired_new:
                changes.append(RawChange("added", "clause", sid, heading, None, n, None, j, 0.0))
        while a < len(old_block):
            if a not in pairs:
                i, o = old_block[a]
                changes.append(RawChange("removed", "clause", sid, heading, o, None, i, None, 0.0))
            a += 1
    return changes


def _section_body(section: Section) -> str:
    return "\n".join(section.clauses) if section.clauses else section.heading


def detect_moves(changes: List[RawChange]) -> List[RawChange]:
    """Merge identical removed+added clause pairs into one "moved" change."""
    removed = {}
    for idx, c in enumerate(changes):
        if c.change_type == "removed" and c.scope == "clause":
            removed.setdefault(normalize_clause(c.old_text), []).append(idx)
    drop = set()
    for idx, c in enumerate(changes):
        if c.change_type == "added" and c.scope == "clause":
            key = normalize_clause(c.new_text)
            if removed.get(key):
                r = removed[key].pop(0)
                old = changes[r]
                c.change_type = "moved"
                c.old_text, c.old_position = old.old_text, old.old_position
                c.similarity = 1.0
                if old.section_id != c.section_id:
                    c.section_heading = f"{old.section_heading or old.section_id} -> {c.section_heading}"
                drop.add(r)
    return [c for i, c in enumerate(changes) if i not in drop]


def diff_documents(old: List[Section], new: List[Section]) -> List[RawChange]:
    changes: List[RawChange] = []
    for o, n in align_sections(old, new):
        changes.extend(diff_sections(o, n))
    return detect_moves(changes)
