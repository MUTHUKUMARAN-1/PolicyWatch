"""Classify a detected change by category and severity.

Rules are deliberately transparent (keyword lists + a points system) so the
team can explain every result in the report, and tests can pin them down.
Every severity comes with ``reasons`` describing which rules fired.

Severity scoring
----------------
* formatting-only / moved          -> "none" / "minor" (fixed)
* magnitude of the wording change  -> 0-2 points
* sensitive category               -> +1
* negation flipped (not/never ...) -> +3
* obligation word changed (may/will/must ...) -> +2
* number / amount / period changed -> +3
* risky term introduced (sell, third parties, arbitration ...) -> +2
* protective term removed (consent, opt out, notify ...)        -> +2
* whole section added/removed      -> +1

Total: 0-1 = minor, 2-3 = moderate, >= 4 = major.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from .normalize import normalize_clause, words

# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------

# Each keyword is matched as a word prefix against the normalised text,
# so "share" also matches "shared"/"sharing".
CATEGORY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "data_sharing": (
        "share", "sharing", "third part", "third-part", "partner", "affiliate", "sell", "sale of",
        "disclose", "disclosure", "transfer", "advertiser", "vendor", "service provider", "broker",
    ),
    "data_collection": (
        "collect", "personal information", "personal data", "information we", "location", "device",
        "ip address", "biometric", "contacts", "usage data", "camera", "microphone",
    ),
    "cookies_tracking": ("cookie", "tracking", "tracker", "pixel", "beacon", "analytics", "fingerprint"),
    "data_retention": ("retain", "retention", "store", "storage", "keep your", "kept", "delete", "deletion", "archive"),
    "security": ("security", "secure", "encrypt", "breach", "safeguard", "unauthori", "password", "protect"),
    "user_rights": (
        "right to", "your rights", "opt out", "opt-out", "opt in", "consent", "withdraw", "access your",
        "rectif", "correct", "portability", "object to", "request",
    ),
    "payments": (
        "payment", "pay", "fee", "price", "pricing", "charge", "billing", "bill", "refund", "subscription",
        "invoice", "credit card", "purchase", "renew", "tax", "$", "rs.", "inr", "usd",
    ),
    "legal": (
        "liabil", "arbitration", "governing law", "jurisdiction", "indemn", "warrant", "dispute", "court",
        "class action", "waive", "waiver", "lawsuit", "legal",
    ),
    "account_termination": ("terminat", "suspend", "suspension", "close your account", "deactivat", "ban"),
    "children": ("child", "minor", "under the age", "under 13", "under 16", "under 18", "parent", "coppa"),
    "communications": ("email", "newsletter", "marketing", "promotional", "notification", "sms", "message"),
    "policy_updates": ("changes to this", "update this", "modify this", "notify you", "effective date", "last updated"),
}

GENERAL_CATEGORY = "general"

# Categories where even a small wording change can matter to users.
SENSITIVE_CATEGORIES = frozenset(
    {"data_sharing", "data_collection", "data_retention", "security", "user_rights", "payments", "legal", "children",
     "account_termination", "cookies_tracking"}
)


def _contains(text: str, keyword: str) -> bool:
    if keyword in ("$",):
        return keyword in text
    if len(keyword) <= 4:
        # Short keywords must be whole words (plus simple endings), so that
        # "fee" does not match "feedback" or "ban" match "banner".
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?:s|es|ed|ing)?(?![a-z0-9])"
    else:
        pattern = r"(?<![a-z0-9])" + re.escape(keyword)
    return re.search(pattern, text) is not None


def categorize(texts: Iterable[Optional[str]], heading: str = "") -> List[str]:
    """Return matching categories, best match first. Falls back to ``["general"]``.

    Heading keywords count double, because the section a clause lives in is
    a strong hint ("Information We Share" -> data_sharing).
    """
    body = " ".join(normalize_clause(t) for t in texts if t)
    head = normalize_clause(heading or "")
    scores: Dict[str, int] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for k in keywords if _contains(body, k)) + 2 * sum(1 for k in keywords if _contains(head, k))
        if score:
            scores[cat] = score
    if not scores:
        return [GENERAL_CATEGORY]
    order = list(CATEGORY_KEYWORDS)
    return sorted(scores, key=lambda c: (-scores[c], order.index(c)))


# --------------------------------------------------------------------------
# Severity signals
# --------------------------------------------------------------------------

NEGATIONS = frozenset({"not", "never", "no", "none", "without", "neither", "nor", "cannot", "can't", "won't",
                       "don't", "doesn't", "isn't", "aren't",
                       # apostrophes are stripped during normalisation:
                       "cant", "wont", "dont", "doesnt", "isnt", "arent", "shouldnt", "wouldnt"})
MODALS = frozenset({"may", "might", "can", "could", "will", "shall", "must", "should", "would"})

RISKY_TERMS = (
    "sell", "third part", "advertis", "broker", "partner", "affiliate", "transfer", "biometric", "location",
    "arbitration", "class action", "waive", "indemnif", "without notice", "at any time", "sole discretion",
    "indefinite", "fee", "charge", "auto-renew", "automatically renew", "non-refundable", "terminate",
    "suspend", "track", "profil", "combine", "monitor",
)
PROTECTIVE_TERMS = (
    "consent", "opt out", "opt-out", "opt in", "notify", "notice", "right to", "encrypt", "anonymi",
    "pseudonymi", "delete", "deletion", "refund", "cancel", "will not sell", "do not sell", "never sell",
    "request", "withdraw", "secure", "protect", "limit",
)

_DATE_STAMP = re.compile(r"^(?:last (?:updated|modified|revised)|effective(?: date| from| as of)?|updated( on)?|revised( on)?|date)\b[^.]{0,40}$")

_NUMBER = re.compile(r"(?:[$₹£€]\s?)?\d+(?:[.,]\d+)*\s?%?")


def _numbers(text: Optional[str]) -> List[str]:
    return sorted(n.replace(" ", "") for n in _NUMBER.findall(text or ""))


_DISPLAY = {
    "advertis": "advertising", "track": "tracking", "profil": "profiling", "indemnif": "indemnify",
    "third part": "third parties", "anonymi": "anonymise", "pseudonymi": "pseudonymise", "indefinite": "indefinitely",
}


def _pretty(terms: Iterable[str]) -> str:
    """Readable, sorted list of matched keyword stems ("advertis" -> "advertising")."""
    return ", ".join(sorted({_DISPLAY.get(t, t) for t in terms}))


def _terms_in(text: Optional[str], terms: Iterable[str]) -> set:
    norm = normalize_clause(text or "")
    return {t for t in terms if _contains(norm, t)}


_STRONG_MODALS = {"will", "shall", "must"}
_WEAK_MODALS = {"may", "might", "can", "could"}


def describe_change(
    change_type: str,
    scope: str,
    old_text: Optional[str],
    new_text: Optional[str],
    heading: str = "",
) -> str:
    """Short plain-English title for a change, e.g. "Number changed: 30 -> 365".

    Written for non-experts (UI cards, notification lines). Picks the most
    important thing that happened, in priority order.
    """
    if change_type == "formatting":
        return "Formatting only: no change in meaning"
    if change_type == "moved":
        return "Same sentence, moved to a different place"
    if scope == "heading":
        return f"Section renamed: '{old_text}' -> '{new_text}'"
    if scope == "section":
        if change_type == "added":
            return f"New section added: '{heading}'"
        return f"Whole section deleted: '{heading}'"

    old_w, new_w = set(words(old_text or "")), set(words(new_text or ""))
    protect_lost = sorted(_terms_in(old_text, PROTECTIVE_TERMS) - _terms_in(new_text, PROTECTIVE_TERMS))
    risky_new = sorted(_terms_in(new_text, RISKY_TERMS) - _terms_in(old_text, RISKY_TERMS))

    if change_type == "removed":
        if protect_lost:
            return f"User protection removed ({_pretty(protect_lost)})"
        return "Sentence deleted"
    if change_type == "added":
        if risky_new:
            return f"New sentence with risky wording ({_pretty(risky_new)})"
        return "New sentence added"

    # modified
    if _DATE_STAMP.match(normalize_clause(old_text or "")) and _DATE_STAMP.match(normalize_clause(new_text or "")):
        return "Only the 'last updated' date changed"
    neg_old, neg_new = old_w & NEGATIONS, new_w & NEGATIONS
    mod_old, mod_new = old_w & MODALS, new_w & MODALS
    if neg_old - neg_new:
        before = " ".join(sorted(mod_old)) + " " + " ".join(sorted(neg_old - neg_new))
        after = " ".join(sorted(mod_new)) or "(no 'not')"
        return f"Meaning reversed: '{before.strip()}' became '{after}'"
    if mod_old & _STRONG_MODALS and mod_new & _WEAK_MODALS and not mod_new & _STRONG_MODALS:
        return f"Promise weakened: '{', '.join(sorted(mod_old))}' -> '{', '.join(sorted(mod_new))}'"
    if neg_new - neg_old:
        return f"Meaning reversed: '{', '.join(sorted(neg_new - neg_old))}' was added"
    if mod_old != mod_new:
        return f"Obligation changed: '{', '.join(sorted(mod_old)) or '-'}' -> '{', '.join(sorted(mod_new)) or '-'}'"
    old_nums, new_nums = _numbers(old_text), _numbers(new_text)
    if old_nums != new_nums:
        gone = [n for n in old_nums if n not in new_nums] or ["-"]
        came = [n for n in new_nums if n not in old_nums] or ["-"]
        return f"Number changed: {', '.join(gone)} -> {', '.join(came)}"
    if protect_lost:
        return f"User protection weakened ({_pretty(protect_lost)})"
    if risky_new:
        return f"New risky wording ({_pretty(risky_new)})"
    return "Wording changed"


def severity_from_score(score: int) -> str:
    if score >= 4:
        return "major"
    if score >= 2:
        return "moderate"
    return "minor"


def assess_severity(
    change_type: str,
    old_text: Optional[str],
    new_text: Optional[str],
    similarity: float,
    categories: List[str],
    scope: str = "clause",
) -> Tuple[str, int, List[str]]:
    """Return ``(severity, score, reasons)`` for one change."""
    if change_type == "formatting":
        return "none", 0, ["Formatting/cosmetic edit only (case, punctuation, quotes); meaning unchanged."]
    if change_type == "moved":
        return "minor", 1, ["Clause moved to a different position; wording unchanged."]

    score = 0
    reasons: List[str] = []

    if scope == "heading":
        reasons.append("Section heading renamed.")
        return "minor", 1, reasons

    if change_type == "modified" and _DATE_STAMP.match(normalize_clause(old_text or "")) \
            and _DATE_STAMP.match(normalize_clause(new_text or "")):
        return "minor", 1, ["Only the policy's 'last updated' / effective date changed."]

    # Magnitude
    if change_type == "modified":
        ratio = 1.0 - similarity
        if ratio >= 0.5:
            score += 2
            reasons.append(f"Clause substantially rewritten ({ratio:.0%} of wording changed).")
        elif ratio >= 0.2:
            score += 1
            reasons.append(f"Clause partly reworded ({ratio:.0%} of wording changed).")
        else:
            reasons.append(f"Small wording change ({ratio:.0%} of wording changed).")
    else:
        text = new_text if change_type == "added" else old_text
        n = len(words(text or ""))
        score += 1
        verb = "added" if change_type == "added" else "removed"
        if scope == "section":
            score += 1
            reasons.append(f"Entire section {verb}.")
        else:
            reasons.append(f"Clause {verb}.")
        if n > 30:
            score += 1
            reasons.append(f"Long passage ({n} words).")

    # Sensitive topic
    sensitive = [c for c in categories if c in SENSITIVE_CATEGORIES]
    if sensitive:
        score += 1
        reasons.append(f"Touches a sensitive topic: {sensitive[0]}.")

    old_words = set(words(old_text or ""))
    new_words = set(words(new_text or ""))

    if change_type == "modified":
        if (old_words & NEGATIONS) != (new_words & NEGATIONS):
            score += 3
            gone = sorted((old_words & NEGATIONS) - new_words)
            came = sorted((new_words & NEGATIONS) - old_words)
            detail = ", ".join([f"removed '{w}'" for w in gone] + [f"added '{w}'" for w in came])
            reasons.append(f"Negation changed ({detail}); meaning may be reversed.")
        if (old_words & MODALS) != (new_words & MODALS):
            score += 2
            reasons.append(
                "Obligation/permission wording changed "
                f"({', '.join(sorted(old_words & MODALS)) or '-'} -> {', '.join(sorted(new_words & MODALS)) or '-'})."
            )
        old_nums, new_nums = _numbers(old_text), _numbers(new_text)
        if old_nums != new_nums:
            score += 3
            reasons.append(f"Number/amount/period changed ({', '.join(old_nums) or '-'} -> {', '.join(new_nums) or '-'}).")

    # Risky terms introduced / protective terms dropped
    risky_new = _terms_in(new_text, RISKY_TERMS) - _terms_in(old_text, RISKY_TERMS)
    if risky_new and change_type in ("added", "modified"):
        score += 2
        reasons.append(f"Introduces potentially user-unfavourable terms: {_pretty(risky_new)}.")
    protect_lost = _terms_in(old_text, PROTECTIVE_TERMS) - _terms_in(new_text, PROTECTIVE_TERMS)
    if protect_lost and change_type in ("removed", "modified"):
        score += 2
        reasons.append(f"Removes user-protective wording: {_pretty(protect_lost)}.")

    return severity_from_score(score), score, reasons
