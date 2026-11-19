"""HTML parser: extracts title, effective date and heading-delimited sections.

Missing fields are returned as None with a warning - values are never invented (CP-2).
Text is normalised (whitespace, typographic quotes/dashes, space-before-punctuation) so that
formatting-only edits do not change the content hash.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

HEADINGS = ["h1", "h2", "h3", "h4"]
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE_PATTERNS = [
    (re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})\b"), "%B %d %Y"),
    (re.compile(rf"\b(\d{{1,2}})\s+({_MONTHS})\s+(\d{{4}})\b"), "%d %B %Y"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "%Y-%m-%d"),
]
_TRANSLATE = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                            "\u2013": "-", "\u2014": "-", "\u00a0": " "})


class ParserError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class Section:
    heading: str
    text: str
    hash: str


@dataclass
class ParsedDoc:
    title: str | None
    effective_date_raw: str | None
    effective_date: str | None            # ISO date if parseable
    sections: list[Section]
    warnings: list[str] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return sum(len(s.text) for s in self.sections)

    @property
    def content_hash(self) -> str:
        payload = json.dumps([self.title, self.effective_date or self.effective_date_raw,
                              [(s.heading, s.hash) for s in self.sections]], ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {"title": self.title, "effective_date_raw": self.effective_date_raw,
                "effective_date": self.effective_date,
                "sections": [{"heading": s.heading, "text": s.text, "hash": s.hash} for s in self.sections]}


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_TRANSLATE)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:!?)])", r"\1", s)
    s = re.sub(r"(\()\s+", r"\1", s)
    return s


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _select_first(soup, selector):
    selectors = [selector] if isinstance(selector, str) else list(selector or [])
    for sel in selectors:
        node = soup.select_one(sel)
        if node is not None:
            return node
    return None


def parse_date(text: str) -> tuple[str | None, str | None]:
    for pat, fmt in _DATE_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group(0)
            try:
                parts = re.sub(r"[,]", "", raw) if fmt != "%Y-%m-%d" else raw
                return raw, datetime.strptime(parts, fmt).date().isoformat()
            except ValueError:
                return raw, None
    return None, None


def parse_policy(html: str, selectors: dict) -> ParsedDoc:
    if not html or not html.strip():
        raise ParserError("empty_response", "response body is empty")
    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []

    body = _select_first(soup, selectors.get("body"))
    if body is None:
        raise ParserError("body_selector_not_found", f"selector {selectors.get('body')!r} matched nothing")
    for bad in body.select("script, style, noscript, template"):
        bad.decompose()
    for sel in selectors.get("ignore", []) or []:
        for bad in body.select(sel):
            bad.decompose()

    title = None
    if selectors.get("title"):
        tnode = _select_first(soup, selectors["title"])
        if tnode is not None and normalize_text(tnode.get_text(" ")):
            title = normalize_text(tnode.get_text(" "))
        else:
            warnings.append("title_missing")

    raw_date = iso_date = None
    if selectors.get("updated"):
        dnode = _select_first(soup, selectors["updated"])
        if dnode is not None:
            raw_date, iso_date = parse_date(normalize_text(dnode.get_text(" ")))
        if raw_date is None:
            warnings.append("effective_date_missing")
        # the date line is metadata, not policy text: keep it out of the section text
        if dnode is not None and body in dnode.parents:
            dnode.decompose()

    head_tags = selectors.get("section_headings") or ["h2", "h3"]
    sections: list[Section] = []
    heading, buf = "(preamble)", []
    counts: dict[str, int] = {}

    def flush():
        text = normalize_text(" ".join(buf))
        if text:
            key = heading
            counts[key] = counts.get(key, 0) + 1
            if counts[key] > 1:
                key = f"{heading} #{counts[key]}"
            sections.append(Section(key, text, _hash(text)))

    for node in body.descendants:
        if isinstance(node, Tag) and node.name in head_tags:
            flush()
            buf = []
            heading = normalize_text(node.get_text(" ")) or "(untitled)"
            continue
        if isinstance(node, NavigableString) and not isinstance(node, Comment):
            if node.find_parent(HEADINGS) is not None:
                continue
            buf.append(str(node))
    flush()

    if not sections:
        raise ParserError("no_content", "body matched but contained no text sections")
    return ParsedDoc(title, raw_date, iso_date, sections, warnings)
