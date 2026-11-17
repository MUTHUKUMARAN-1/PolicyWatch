"""Unit tests for PolicyWatch Part 6 - Change Detection and Classification.

Run from the repo root with either:
    python -m unittest discover -s change_detection/tests -t . -v
    python -m pytest change_detection/tests -v
"""

import json
import unittest
from pathlib import Path

from change_detection import (
    ChangeReport,
    content_hash,
    detect_changes,
    has_meaningful_change,
    parse_document,
)
from change_detection.classifier import assess_severity, categorize
from change_detection.normalize import html_to_text, normalize_clause, split_sentences

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def only(report, **attrs):
    """Return the changes matching all given attribute values."""
    return [c for c in report.changes if all(getattr(c, k) == v for k, v in attrs.items())]


# ---------------------------------------------------------------------------
# Parsing / normalisation
# ---------------------------------------------------------------------------

class TestParsing(unittest.TestCase):
    def test_plain_text_sections_and_clauses(self):
        doc = "Intro line here.\n\n1. Information We Collect\nWe collect email. We collect name.\n\nCOOKIES\nWe use cookies."
        sections = parse_document(doc)
        self.assertEqual([s.section_id for s in sections], ["preamble", "information-we-collect", "cookies"])
        self.assertEqual(sections[1].clauses, ["We collect email.", "We collect name."])

    def test_html_strips_scripts_nav_footer(self):
        html = "<nav>Menu</nav><h2>Data</h2><p>We keep data.</p><script>evil()</script><footer>(c)</footer>"
        text = html_to_text(html)
        self.assertNotIn("evil", text)
        self.assertNotIn("Menu", text)
        self.assertIn("## Data", text)

    def test_html_list_items_become_clauses(self):
        sections = parse_document("<h2>Rights</h2><ul><li>Access your data.</li><li>Opt out.</li></ul>")
        self.assertEqual(sections[0].clauses, ["Access your data.", "Opt out."])

    def test_numbered_sentence_is_not_heading(self):
        sections = parse_document("Terms\n\n1. We collect your data.\n2. We share it.")
        self.assertEqual(len(sections), 1)
        self.assertEqual(len(sections[0].clauses), 2)

    def test_sentence_split_keeps_abbreviations(self):
        self.assertEqual(split_sentences("We use data, e.g. Email and name. Then more."),
                         ["We use data, e.g. Email and name.", "Then more."])

    def test_normalize_ignores_cosmetics(self):
        self.assertEqual(normalize_clause("We  “DON’T” sell data."), normalize_clause('we "don\'t" sell data'))

    def test_section_id_ignores_numbering(self):
        a = parse_document("2. Sharing\nWe share.")[0].section_id
        b = parse_document("3. Sharing\nWe share.")[0].section_id
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

class TestDetection(unittest.TestCase):
    def test_identical_documents_have_no_changes(self):
        text = (SAMPLES / "terms_v1.txt").read_text(encoding="utf-8")
        report = detect_changes(text, text)
        self.assertFalse(report.has_changes)
        self.assertEqual(report.max_severity, "none")
        self.assertEqual(report.headline(), "No changes detected.")

    def test_whitespace_only_change_is_ignored_completely(self):
        report = detect_changes("Data\nWe keep your data.", "Data\nWe   keep  your\n data.")
        self.assertEqual(report.changes, [])

    def test_formatting_only_change(self):
        report = detect_changes("Data\nWe keep your data.", "Data\nWe keep your Data")
        self.assertEqual(len(report.changes), 1)
        c = report.changes[0]
        self.assertEqual(c.change_type, "formatting")
        self.assertEqual(c.severity, "none")
        self.assertTrue(c.is_cosmetic)
        self.assertFalse(report.has_significant_changes)

    def test_include_formatting_false_drops_cosmetic(self):
        report = detect_changes("Data\nWe keep your data.", "Data\nWe keep your Data", include_formatting=False)
        self.assertEqual(report.changes, [])

    def test_added_clause(self):
        report = detect_changes("Sharing\nWe share with vendors.",
                                "Sharing\nWe share with vendors. We sell data to brokers.")
        added = only(report, change_type="added")
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].new_text, "We sell data to brokers.")
        self.assertIsNone(added[0].old_text)
        self.assertEqual(added[0].scope, "clause")

    def test_removed_clause(self):
        report = detect_changes("Rights\nYou can opt out. You can access data.", "Rights\nYou can access data.")
        removed = only(report, change_type="removed")
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].old_text, "You can opt out.")

    def test_modified_clause_has_inline_diff(self):
        report = detect_changes("Retention\nWe retain data for 30 days.", "Retention\nWe retain data for 90 days.")
        self.assertEqual(len(report.changes), 1)
        c = report.changes[0]
        self.assertEqual(c.change_type, "modified")
        ops = [(s.op, s.text) for s in c.inline_diff]
        self.assertIn(("delete", "30"), ops)
        self.assertIn(("insert", "90"), ops)
        self.assertGreater(c.similarity, 0.7)

    def test_added_and_removed_sections(self):
        old = "Intro\nHello there.\n\nChildren\nWe do not serve kids under 13."
        new = "Intro\nHello there.\n\nCookies\nWe use cookies."
        report = detect_changes(old, new)
        self.assertEqual(len(only(report, change_type="added", scope="section")), 1)
        self.assertEqual(len(only(report, change_type="removed", scope="section")), 1)

    def test_renamed_section_is_matched_not_added(self):
        old = "How We Share Data\nWe share with vendors to run the app. We never sell your data."
        new = "Sharing Your Data\nWe share with vendors to run the app. We never sell your data."
        report = detect_changes(old, new)
        self.assertEqual(len(report.changes), 1)
        self.assertEqual(report.changes[0].scope, "heading")
        self.assertEqual(report.changes[0].change_type, "modified")

    def test_renumbered_heading_is_formatting(self):
        report = detect_changes("2. Contact\nEmail us.", "3. Contact\nEmail us.")
        self.assertEqual([c.change_type for c in report.changes], ["formatting"])

    def test_moved_clause(self):
        old = "Alpha\nFirst rule here. Second rule here.\n\nBeta\nThird rule here."
        new = "Alpha\nSecond rule here.\n\nBeta\nThird rule here. First rule here."
        report = detect_changes(old, new)
        moved = only(report, change_type="moved")
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0].severity, "minor")
        self.assertEqual(len(report.changes), 1)

    def test_html_vs_text_markup_changes_ignored(self):
        html = "<h2>Data</h2><p>We keep <b>your</b> data.</p>"
        text = "Data\nWe keep your data."
        self.assertEqual(detect_changes(html, text).changes, [])

    def test_min_severity_filter(self):
        old = "Fees\nPremium costs $10. We may email you."
        new = "Fees\nPremium costs $20. We may email you!"
        report = detect_changes(old, new, min_severity="moderate")
        self.assertTrue(all(c.severity in ("moderate", "major") for c in report.changes))
        self.assertEqual(len(report.changes), 1)

    def test_empty_inputs(self):
        report = detect_changes("", "Data\nWe collect email.")
        self.assertEqual(len(report.changes), 1)
        self.assertEqual(report.changes[0].change_type, "added")
        self.assertEqual(detect_changes("", "").changes, [])


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestClassification(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(categorize(["We may sell your data to third parties."])[0], "data_sharing")
        self.assertEqual(categorize(["Refunds are not available for subscription fees."])[0], "payments")
        self.assertEqual(categorize(["Disputes go to binding arbitration."])[0], "legal")
        self.assertEqual(categorize(["We use cookies and pixels."])[0], "cookies_tracking")
        self.assertEqual(categorize(["Hello world."]), ["general"])

    def test_short_keywords_match_whole_words_only(self):
        self.assertEqual(categorize(["We receive feedback from users."]), ["general"])
        self.assertEqual(categorize(["We show a banner."]), ["general"])
        self.assertEqual(categorize(["Late fees apply."])[0], "payments")

    def test_heading_influences_category(self):
        self.assertEqual(categorize(["We keep it for a while."], heading="Data Retention")[0], "data_retention")

    def test_typo_fix_is_minor(self):
        report = detect_changes("About\nWe recieve feedback from users.", "About\nWe receive feedback from users.")
        self.assertEqual(report.changes[0].severity, "minor")

    def test_negation_flip_is_major(self):
        report = detect_changes("Sharing\nWe will not sell your personal data.",
                                "Sharing\nWe will sell your personal data.")
        c = report.changes[0]
        self.assertEqual(c.severity, "major")
        self.assertTrue(any("Negation" in r for r in c.reasons))

    def test_modal_change_is_flagged(self):
        sev, score, reasons = assess_severity("modified", "We will notify you.", "We may notify you.", 0.75, ["general"])
        self.assertIn(sev, ("moderate", "major"))
        self.assertTrue(any("Obligation" in r for r in reasons))

    def test_price_change_is_major(self):
        report = detect_changes("Fees\nPremium costs $10 per month.", "Fees\nPremium costs $15 per month.")
        c = report.changes[0]
        self.assertEqual((c.category, c.severity), ("payments", "major"))

    def test_last_updated_date_is_minor(self):
        report = detect_changes("Last updated: Jan 1, 2026.", "Last updated: Nov 2, 2026.")
        self.assertEqual(report.changes[0].severity, "minor")

    def test_removed_protection_is_major(self):
        report = detect_changes("Rights\nYou can opt out of marketing. You can access data.",
                                "Rights\nYou can access data.")
        self.assertEqual(only(report, change_type="removed")[0].severity, "major")

    def test_neutral_added_clause_is_moderate_or_less(self):
        report = detect_changes("Contact\nEmail us.", "Contact\nEmail us. Our office is in Chennai.")
        self.assertIn(report.changes[0].severity, ("minor", "moderate"))

    def test_every_change_has_reasons(self):
        report = self._sample_report()
        self.assertTrue(all(c.reasons for c in report.changes))

    def test_plain_english_titles(self):
        titles = {c.title for c in self._sample_report().changes}
        self.assertIn("Meaning reversed: 'will not' became 'may'", titles)
        self.assertIn("Number changed: 30 -> 365", titles)
        self.assertIn("User protection removed (opt out)", titles)
        self.assertIn("Formatting only: no change in meaning", titles)
        r = detect_changes("Termination\nWe will notify you before we suspend your account.",
                           "Termination\nWe may suspend your account at any time without notice.")
        self.assertEqual(r.changes[0].title, "Promise weakened: 'will' -> 'may'")

    def _sample_report(self):
        return detect_changes((SAMPLES / "privacy_v1.html").read_text(encoding="utf-8"),
                              (SAMPLES / "privacy_v2.html").read_text(encoding="utf-8"),
                              document_id="exampleapp-privacy", old_version_id="v1", new_version_id="v2")


# ---------------------------------------------------------------------------
# End-to-end on sample policies + interface for other parts
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = detect_changes(
            (SAMPLES / "privacy_v1.html").read_text(encoding="utf-8"),
            (SAMPLES / "privacy_v2.html").read_text(encoding="utf-8"),
            document_id="exampleapp-privacy", old_version_id="v1", new_version_id="v2",
        )

    def test_expected_changes_found(self):
        r = self.report
        sell = [c for c in r.changes if c.new_text and "sell" in c.new_text]
        self.assertEqual(len(sell), 1)
        self.assertEqual((sell[0].change_type, sell[0].category, sell[0].severity),
                         ("modified", "data_sharing", "major"))
        cookies = only(r, change_type="added", scope="section")
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0].category, "cookies_tracking")
        retention = [c for c in r.changes if c.section_id == "data-retention"]
        self.assertEqual(retention[0].severity, "major")
        opt_out = [c for c in r.changes if c.old_text == "You can opt out of marketing emails."]
        self.assertEqual(opt_out[0].change_type, "removed")
        # Curly quotes in "Contact Us" are cosmetic.
        contact = [c for c in r.changes if c.section_id == "contact-us"]
        self.assertTrue(all(c.severity == "none" for c in contact))
        # Unchanged clause is not reported.
        self.assertFalse(any((c.old_text or "").startswith("We share data with service providers") for c in r.changes))

    def test_summary_shape(self):
        s = self.report.summary()
        for key in ("total_changes", "significant_changes", "max_severity", "significance_score",
                    "by_type", "by_severity", "by_category", "headline"):
            self.assertIn(key, s)
        self.assertEqual(s["max_severity"], "major")
        self.assertEqual(s["total_changes"], sum(s["by_type"].values()))

    def test_json_round_trip(self):
        data = json.loads(self.report.to_json())
        rebuilt = ChangeReport.from_dict(data)
        self.assertEqual(rebuilt.to_dict(), self.report.to_dict())
        self.assertEqual(data["document_id"], "exampleapp-privacy")

    def test_db_rows(self):
        rows = self.report.to_rows()
        self.assertEqual(len(rows), len(self.report.changes))
        for row in rows:
            self.assertEqual(row["new_version_id"], "v2")
            for v in row.values():
                self.assertIsInstance(v, (str, int, float, type(None)))

    def test_change_ids_stable_and_unique(self):
        again = detect_changes(
            (SAMPLES / "privacy_v1.html").read_text(encoding="utf-8"),
            (SAMPLES / "privacy_v2.html").read_text(encoding="utf-8"),
            document_id="exampleapp-privacy",
        )
        ids = [c.change_id for c in self.report.changes]
        self.assertEqual(ids, [c.change_id for c in again.changes])
        self.assertEqual(len(ids), len(set(ids)))

    def test_filter_for_notifications(self):
        majors = self.report.filter(min_severity="major", categories=["payments"])
        self.assertTrue(majors)
        self.assertTrue(all(c.severity == "major" and "payments" in c.categories for c in majors))

    def test_text_sample(self):
        r = detect_changes((SAMPLES / "terms_v1.txt").read_text(encoding="utf-8"),
                           (SAMPLES / "terms_v2.txt").read_text(encoding="utf-8"))
        term = [c for c in r.changes if c.section_id == "termination"]
        self.assertEqual(len(term), 1)
        self.assertEqual((term[0].change_type, term[0].severity), ("modified", "major"))
        self.assertTrue(any(c.category == "legal" and c.scope == "section" for c in r.changes))


class TestHashing(unittest.TestCase):
    def test_hash_ignores_cosmetics(self):
        self.assertEqual(content_hash("<h2>Data</h2><p>We keep data.</p>"), content_hash("DATA\nwe keep data"))

    def test_has_meaningful_change(self):
        self.assertFalse(has_meaningful_change("Data\nWe keep data.", "Data\nWe  keep data"))
        self.assertTrue(has_meaningful_change("Data\nWe keep data.", "Data\nWe sell data."))


class TestCLI(unittest.TestCase):
    def test_cli_json(self):
        import contextlib
        import io

        from change_detection.__main__ import main

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([str(SAMPLES / "terms_v1.txt"), str(SAMPLES / "terms_v2.txt"), "--json"])
        self.assertEqual(code, 0)
        self.assertIn("changes", json.loads(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
