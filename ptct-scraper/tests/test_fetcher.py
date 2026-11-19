import requests

from ptct.fetcher import Fetcher, RobotsPolicy


class Resp:
    def __init__(self, code, text="<html>ok " + "x" * 50 + "</html>", headers=None):
        self.status_code, self.text, self.headers = code, text, headers or {}


class FakeSession:
    def __init__(self, seq):
        self.seq, self.calls = list(seq), []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers, timeout))
        item = self.seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make(seq, **kw):
    sleeps = []
    f = Fetcher("TestBot/1.0 (contact)", timeout=5, min_interval=10, max_retries=3, backoff_base=2,
                session=FakeSession(seq), sleep=sleeps.append, clock=lambda: 0.0, **kw)
    return f, sleeps


def test_sends_user_agent_and_timeout():
    f, _ = make([Resp(200)])
    assert f.fetch("https://x.test/p").ok
    _, headers, timeout = f.session.calls[0]
    assert headers["User-Agent"].startswith("TestBot") and timeout == 5


def test_retries_transient_with_exponential_backoff():
    f, sleeps = make([Resp(503), requests.Timeout(), Resp(200)])
    res = f.fetch("https://x.test/p")
    assert res.ok and res.attempts == 3
    assert [s for s in sleeps if s in (2, 4, 8)] == [2, 4]


def test_gives_up_after_max_retries():
    f, _ = make([Resp(500)] * 4)
    res = f.fetch("https://x.test/p")
    assert not res.ok and res.attempts == 4 and len(f.session.calls) == 4


def test_429_stops_immediately_and_records_retry_after():
    f, _ = make([Resp(429, headers={"Retry-After": "120"}), Resp(200)])
    res = f.fetch("https://x.test/p")
    assert res.status == "rate_limited" and res.retry_after == "120" and len(f.session.calls) == 1


def test_403_stops_immediately():
    f, _ = make([Resp(403), Resp(200)])
    assert f.fetch("https://x.test/p").status == "forbidden" and len(f.session.calls) == 1


def test_404_no_retry():
    f, _ = make([Resp(404), Resp(200)])
    res = f.fetch("https://x.test/p")
    assert res.status == "http_error" and res.http_code == 404 and len(f.session.calls) == 1


def test_captcha_page_is_blocked_not_bypassed():
    f, _ = make([Resp(200, "<html>Please solve the CAPTCHA to continue</html>")])
    assert f.fetch("https://x.test/p").status == "blocked_challenge"


def test_robots_disallow_blocks_request():
    rob = RobotsPolicy("TestBot/1.0", session=FakeSession([Resp(200, "User-agent: *\nDisallow: /private\n")]))
    f, _ = make([Resp(200)], robots=rob)
    assert f.fetch("https://x.test/private/policy").status == "blocked_robots"
    assert f.session.calls == []                       # never requested the page
    assert rob.allowed("https://x.test/privacy")


def test_robots_unreachable_is_conservative():
    rob = RobotsPolicy("TestBot/1.0", session=FakeSession([Resp(503)]))
    assert rob.allowed("https://y.test/privacy") is False


def test_robots_404_means_allowed():
    rob = RobotsPolicy("TestBot/1.0", session=FakeSession([Resp(404)]))
    assert rob.allowed("https://z.test/privacy") is True


def test_min_interval_throttle():
    t = [0.0]
    sleeps = []
    f = Fetcher("TestBot/1.0", min_interval=10, session=FakeSession([Resp(200), Resp(200)]),
                sleep=sleeps.append, clock=lambda: t[0])
    f.fetch("https://x.test/a")
    t[0] = 3.0
    f.fetch("https://x.test/b")
    assert sleeps == [7.0]
