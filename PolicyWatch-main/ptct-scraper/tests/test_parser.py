import pytest

from ptct.parser import ParserError, normalize_text, parse_date, parse_policy


def sel(settings, sid):
    return next(s for s in settings.sources if s.id == sid).selectors


def test_extracts_fields_privacy(settings, fx):
    doc = parse_policy(fx("privacy_v1.html"), sel(settings, "acme-privacy"))
    assert doc.title == "Privacy Policy"
    assert doc.effective_date == "2026-01-01"
    assert [s.heading for s in doc.sections] == ["Information We Collect", "How We Use Information",
                                                "Sharing", "Data Retention", "Your Rights"]
    assert "30 days" in doc.sections[3].text


def test_extracts_fields_terms_other_layout(settings, fx):
    doc = parse_policy(fx("terms_v1.html"), sel(settings, "acme-terms"))
    assert doc.title == "Terms of Service"
    assert doc.effective_date == "2026-01-01"
    assert len(doc.sections) == 5


def test_missing_date_is_none_not_invented():
    html = "<main id='b'><h2>A</h2><p>" + "text " * 60 + "</p></main>"
    doc = parse_policy(html, {"body": "#b", "updated": ".nope", "title": "h1"})
    assert doc.effective_date is None and doc.effective_date_raw is None
    assert "effective_date_missing" in doc.warnings and "title_missing" in doc.warnings


def test_selector_not_found_raises():
    with pytest.raises(ParserError) as e:
        parse_policy("<div>hello</div>", {"body": "#policy"})
    assert e.value.code == "body_selector_not_found"


def test_empty_body_raises():
    with pytest.raises(ParserError) as e:
        parse_policy("<main id='b'></main>", {"body": "#b"})
    assert e.value.code == "no_content"


def test_selector_fallback_list():
    doc = parse_policy("<article><h2>X</h2><p>hello world</p></article>", {"body": ["#nope", "article"]})
    assert doc.sections[0].heading == "X"


def test_formatting_does_not_change_hash(settings, fx):
    a = parse_policy(fx("privacy_v1.html"), sel(settings, "acme-privacy"))
    b = parse_policy(fx("privacy_markup_only.html"), sel(settings, "acme-privacy"))
    c = parse_policy(fx("privacy_whitespace_only.html"), sel(settings, "acme-privacy"))
    assert a.content_hash == b.content_hash == c.content_hash


def test_wording_change_changes_hash(settings, fx):
    a = parse_policy(fx("privacy_v1.html"), sel(settings, "acme-privacy"))
    b = parse_policy(fx("privacy_retention_edit.html"), sel(settings, "acme-privacy"))
    assert a.content_hash != b.content_hash


def test_normalize_text():
    assert normalize_text("  don\u2019t \u2014 stop \n now ,ok ") == "don't - stop now,ok"


@pytest.mark.parametrize("txt,iso", [("Last updated: March 5, 2026", "2026-03-05"),
                                      ("Effective 5 March 2026", "2026-03-05"),
                                      ("Effective 2026-03-05", "2026-03-05")])
def test_parse_date(txt, iso):
    assert parse_date(txt)[1] == iso
