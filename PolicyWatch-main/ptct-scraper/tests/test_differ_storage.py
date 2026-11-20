from ptct.differ import diff_versions
from ptct.parser import parse_policy


def sel(settings):
    return next(s for s in settings.sources if s.id == "acme-privacy").selectors


def test_edit_gives_before_after_snippets(settings, fx):
    old = parse_policy(fx("privacy_v1.html"), sel(settings))
    new = parse_policy(fx("privacy_retention_edit.html"), sel(settings))
    ch = diff_versions(old.to_dict(), new)
    assert [c.category for c in ch] == ["section_edited"]
    assert "30 days" in ch[0].before and "90 days" in ch[0].after and ch[0].section == "Data Retention"


def test_removed_section_detected(settings, fx):
    old = parse_policy(fx("privacy_v1.html"), sel(settings))
    new = parse_policy(fx("privacy_section_removed.html"), sel(settings))
    ch = diff_versions(old.to_dict(), new)
    assert [(c.category, c.section) for c in ch] == [("section_removed", "Sharing")]


def test_rename_not_remove_plus_add(settings, fx):
    old = parse_policy(fx("privacy_v1.html"), sel(settings))
    new = parse_policy(fx("privacy_heading_renamed.html"), sel(settings))
    assert [c.category for c in diff_versions(old.to_dict(), new)] == ["section_renamed"]
