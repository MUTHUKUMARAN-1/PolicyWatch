import pytest
import yaml

from ptct.config import ConfigError, load_config


def write(tmp_path, d):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(d))
    return p


def base():
    return {"crawl": {"user_agent": "Bot/1 (x)"},
            "sources": [{"id": "a", "company": "A", "doc_type": "privacy_policy", "url": "https://a.test/p",
                         "refresh_hours": 24, "approval_status": "APPROVED", "selectors": {"body": "main"}}]}


def test_valid(tmp_path):
    s = load_config(write(tmp_path, base()))
    assert len(s.live_sources()) == 1


def test_requires_user_agent(tmp_path):
    d = base(); d["crawl"]["user_agent"] = ""
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, d))


def test_rejects_non_http_and_dupes(tmp_path):
    d = base(); d["sources"][0]["url"] = "file:///etc/passwd"
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, d))
    d = base(); d["sources"].append(dict(d["sources"][0]))
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, d))


def test_unapproved_not_live(tmp_path):
    d = base(); d["sources"][0]["approval_status"] = "PENDING_MENTOR_APPROVAL"
    assert load_config(write(tmp_path, d)).live_sources() == []
