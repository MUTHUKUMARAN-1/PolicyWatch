"""Respectful HTTP requester (Section 6 of the SRS).

- descriptive User-Agent, explicit timeout, minimum interval between requests
- robots.txt checked before every host's first request
- retry with exponential backoff on transient failure (5xx / timeout / connection)
- STOPS on 403 / 429 (records Retry-After); never retries or works around them
- CAPTCHA / bot-challenge pages are detected and treated as blocked, never bypassed
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from .timeutil import iso, utc_now

_CHALLENGE_RE = re.compile(r"(captcha|cf-chl|are you a robot|verify you are human|unusual traffic)", re.I)


@dataclass
class FetchResult:
    url: str
    status: str                 # ok | http_error | forbidden | rate_limited | blocked_robots |
                                # blocked_challenge | timeout | network_error
    http_code: int | None = None
    text: str | None = None
    attempted_at: str = ""
    attempts: int = 0
    retry_after: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class RobotsPolicy:
    """robots.txt check following RFC 9309 behaviour: 4xx -> allowed, 5xx/unreachable -> disallowed."""

    def __init__(self, user_agent: str, session=None, timeout: float = 15):
        self.ua = user_agent
        self.session = session or requests.Session()
        self.timeout = timeout
        self._cache: dict[str, RobotFileParser | bool] = {}

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._cache:
            self._cache[origin] = self._load(origin)
        entry = self._cache[origin]
        if isinstance(entry, bool):
            return entry
        return entry.can_fetch(self.ua, url)

    def _load(self, origin: str):
        try:
            r = self.session.get(origin + "/robots.txt", headers={"User-Agent": self.ua}, timeout=self.timeout)
        except requests.RequestException:
            return False
        if 400 <= r.status_code < 500:
            return True
        if r.status_code >= 500:
            return False
        rp = RobotFileParser()
        rp.parse(r.text.splitlines())
        return rp


class Fetcher:
    def __init__(self, user_agent: str, timeout: float = 15, min_interval: float = 10,
                 max_retries: int = 3, backoff_base: float = 2, session=None,
                 sleep=time.sleep, clock=time.monotonic, robots=None):
        self.ua = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.session = session or requests.Session()
        self._sleep = sleep
        self._clock = clock
        self.robots = robots
        self._last_request: dict[str, float] = {}

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self.min_interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._clock()

    def fetch(self, url: str) -> FetchResult:
        res = FetchResult(url=url, status="network_error", attempted_at=iso(utc_now()))
        if self.robots is not None and not self.robots.allowed(url):
            res.status = "blocked_robots"
            res.error = "disallowed by robots.txt (or robots.txt unavailable)"
            return res

        host = urlparse(url).netloc
        for attempt in range(1, self.max_retries + 2):
            res.attempts = attempt
            self._throttle(host)
            try:
                r = self.session.get(url, headers={"User-Agent": self.ua}, timeout=self.timeout)
            except requests.Timeout:
                res.status, res.error = "timeout", "request timed out"
            except requests.RequestException as e:
                res.status, res.error = "network_error", str(e)[:200]
            else:
                res.http_code = r.status_code
                if r.status_code == 429:
                    res.status, res.error = "rate_limited", "HTTP 429 - stopping, not retrying"
                    res.retry_after = r.headers.get("Retry-After")
                    return res
                if r.status_code == 403:
                    res.status, res.error = "forbidden", "HTTP 403 - stopping, not retrying"
                    return res
                if r.status_code >= 500:
                    res.status, res.error = "http_error", f"HTTP {r.status_code} (transient)"
                elif r.status_code != 200:
                    res.status, res.error = "http_error", f"HTTP {r.status_code}"
                    return res
                else:
                    body = r.text or ""
                    if len(body) < 20000 and _CHALLENGE_RE.search(body[:5000]):
                        res.status, res.error = "blocked_challenge", "bot challenge/CAPTCHA page - not bypassed"
                        return res
                    res.status, res.text, res.error = "ok", body, None
                    return res
            if attempt <= self.max_retries:
                self._sleep(self.backoff_base * (2 ** (attempt - 1)))
        return res


class OfflineFetcher:
    """Serves scripted (http_code, html) responses - used for reproducible offline tests/demo."""

    def __init__(self, script: dict[str, list[tuple[int, str]]]):
        self.script = {u: list(v) for u, v in script.items()}

    def fetch(self, url: str) -> FetchResult:
        queue = self.script.get(url)
        res = FetchResult(url=url, status="network_error", attempted_at=iso(utc_now()), attempts=1)
        if not queue:
            res.error = "no offline response scripted"
            return res
        code, text = queue.pop(0) if len(queue) > 1 else queue[0]
        res.http_code = code
        if code == 200:
            res.status, res.text = "ok", text
        elif code == 429:
            res.status, res.error = "rate_limited", "HTTP 429"
        elif code == 403:
            res.status, res.error = "forbidden", "HTTP 403"
        else:
            res.status, res.error = "http_error", f"HTTP {code}"
        return res
