"""Turn raw scraped policy content (HTML or plain text) into sections and clauses.

Pipeline:  raw HTML/text  ->  clean text with "## " heading markers
           ->  list[Section] (heading + ordered clauses)

A *clause* is one sentence or one list item. Comparing at clause level keeps
diffs small and readable, rather than flagging a whole paragraph when one
sentence in it changed.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List

# --------------------------------------------------------------------------
# HTML -> text
# --------------------------------------------------------------------------

_BLOCK_TAGS = {
    "p", "div", "section", "article", "main", "br", "tr", "table", "ul", "ol",
    "blockquote", "pre", "dl", "dt", "dd", "header", "hr",
}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "svg", "form", "button", "iframe", "head"}


class _HTMLToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip_depth = 0
        self._in_heading = False

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _HEADING_TAGS:
            self.parts.append("\n\n## ")
            self._in_heading = True
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in _HEADING_TAGS:
            self.parts.append("\n\n")
            self._in_heading = False
        elif tag in _BLOCK_TAGS or tag == "li":
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in ("br", "hr") and not self._skip_depth:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_heading:
            data = data.replace("\n", " ")
        self.parts.append(data)


def looks_like_html(content: str) -> bool:
    return bool(re.search(r"<\s*(html|body|p|div|h[1-6]|li|section|article|span)\b", content, re.I))


def html_to_text(html: str) -> str:
    """Strip tags/scripts/nav and keep headings (as ``## ``) and paragraph breaks."""
    parser = _HTMLToText()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    # Collapse whitespace inside lines, then excessive blank lines.
    lines = [re.sub(r"[ \t\r\f\v ]+", " ", ln).strip() for ln in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------

_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
    "…": "...",
})


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_clause(text: str) -> str:
    """Canonical form used to decide whether two clauses mean the same thing.

    Ignores whitespace, letter case, curly vs straight quotes, dash styles,
    list bullets and trailing punctuation: all cosmetic.
    """
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    text = re.sub(r"^\s*(?:[-*•●]|\(?[a-z0-9]{1,3}[.)])\s+", "", text)  # bullets / (a) / 1.
    text = re.sub(r"[\"'`]", "", text)
    text = re.sub(r"\s*([,;:.!?])\s*", r"\1 ", text)
    text = collapse_ws(text)
    return text.rstrip(" .;:,!")


def words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9$%]+(?:[.'-][a-z0-9]+)*", normalize_clause(text))


def content_hash(content: str) -> str:
    """SHA-256 of the normalised document.

    Cosmetic edits (whitespace, case, quote style, HTML markup) do not change
    the hash, so the Freshness tracker can call this on every scrape and only
    run full change detection when the hash differs from the stored one.
    """
    sections = parse_document(content)
    canon = "\n".join(
        normalize_clause(s.heading) + "\n" + "\n".join(normalize_clause(c) for c in s.clauses) for s in sections
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Text -> sections / clauses
# --------------------------------------------------------------------------

@dataclass
class Section:
    section_id: str  # stable slug from heading, numbering stripped
    heading: str  # heading as displayed ("" for text before the first heading)
    clauses: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.clauses)


_NUMBER_PREFIX = re.compile(r"^\s*(?:section\s+|article\s+|clause\s+)?(?:\d+(?:\.\d+)*\.?|[ivxlc]+\.|[a-z]\.|\(\w{1,3}\))\s+", re.I)
_LIST_ITEM = re.compile(r"^\s*(?:[-*•●]|\(?[a-z0-9]{1,3}[.)])\s+\S", re.I)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[\"'(\[]?[A-Z0-9])")
_ENUM_ONLY = re.compile(r"^\(?[a-z0-9]{1,3}[.)]$", re.I)
_ABBREVIATIONS = re.compile(r"\b(?:e\.g|i\.e|etc|inc|ltd|co|corp|mr|mrs|ms|dr|no|vs|u\.s|st)\.$", re.I)


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("#"):
        return True
    if re.match(r"^[-*•●]\s", s):
        return False  # bullet list item, never a heading
    if len(s) > 90 or len(s.split()) > 12:
        return False
    if s[-1] in ".;,!?" and not re.fullmatch(r"(?:section\s+)?\d+(?:\.\d+)*\.", s, re.I):
        return False
    if _NUMBER_PREFIX.match(s) and not re.match(r"^\s*(?:[-*•]|\([a-z]\))", s, re.I):
        rest = _NUMBER_PREFIX.sub("", s)
        return bool(rest) and rest[0].isupper()
    letters = [ch for ch in s if ch.isalpha()]
    if letters and len(letters) >= 3 and all(ch.isupper() for ch in letters):
        return True  # ALL CAPS HEADING
    if s.endswith(":") and len(s.split()) <= 8:
        return True
    # Short Title Case line with no closing punctuation: "How We Share Data".
    tokens = re.findall(r"[A-Za-z][\w'-]*", s)
    if tokens and len(tokens) <= 8 and s[0].isupper() and s[-1] not in ".;,!?\"')":
        significant = [t for t in tokens if t.lower() not in _SMALL_WORDS]
        if significant and all(t[0].isupper() for t in significant):
            return True
    return False


_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with", "we", "you", "your", "our", "us"}


def _clean_heading(line: str) -> str:
    return collapse_ws(line.strip().lstrip("#").strip().rstrip(":"))


def slugify(heading: str) -> str:
    base = _NUMBER_PREFIX.sub("", heading)
    base = normalize_clause(base)
    slug = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return slug or "preamble"


def split_sentences(paragraph: str) -> List[str]:
    pieces = _SENTENCE_SPLIT.split(collapse_ws(paragraph))
    merged: List[str] = []
    for p in pieces:
        # "1." / "(a)" / "e.g." left dangling at the end of a piece belongs with the next one.
        if merged and (_ABBREVIATIONS.search(merged[-1]) or _ENUM_ONLY.match(merged[-1])):
            merged[-1] = merged[-1] + " " + p
        else:
            merged.append(p)
    return [m for m in merged if m.strip()]


def parse_document(content: str, content_type: str = "auto") -> List[Section]:
    """Split a policy (HTML or text) into ordered sections of clauses.

    ``content_type`` may be ``"auto"``, ``"html"`` or ``"text"``.
    """
    if content_type == "html" or (content_type == "auto" and looks_like_html(content)):
        content = html_to_text(content)
    content = unicodedata.normalize("NFKC", content).replace("\r\n", "\n").replace("\r", "\n")

    sections: List[Section] = [Section("preamble", "")]
    paragraph: List[str] = []

    def flush() -> None:
        if paragraph:
            sections[-1].clauses.extend(split_sentences(" ".join(paragraph)))
            paragraph.clear()

    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if _is_heading(line):
            flush()
            heading = _clean_heading(line)
            if heading:
                sections.append(Section("", heading))
            continue
        if _LIST_ITEM.match(line):
            flush()
            # Drop symbol bullets ("- ", "* ", "•"); keep "(a)" / "1." numbering.
            item = re.sub(r"^[-*•●]\s+", "", line)
            sections[-1].clauses.extend(split_sentences(item))
            continue
        paragraph.append(line)
    flush()

    # Drop an empty preamble; assign unique ids.
    sections = [s for s in sections if s.heading or s.clauses]
    seen: dict = {}
    for s in sections:
        base = slugify(s.heading) if s.heading else "preamble"
        seen[base] = seen.get(base, 0) + 1
        s.section_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
    return sections
