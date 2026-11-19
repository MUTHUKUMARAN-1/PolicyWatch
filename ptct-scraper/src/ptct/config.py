"""Configuration loading (FR-01): approved URLs, refresh frequency, field map, crawl limits."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml


class ConfigError(Exception):
    pass


@dataclass
class Source:
    id: str
    company: str
    doc_type: str            # privacy_policy | terms_of_service
    url: str
    refresh_hours: int
    selectors: dict
    approval_status: str     # APPROVED only after written mentor approval (CP-1)
    fixture: str | None = None


@dataclass
class Settings:
    user_agent: str
    timeout: float
    min_interval: float
    max_retries: int
    backoff_base: float
    max_pages_per_run: int
    min_body_chars: int
    sources: list[Source] = field(default_factory=list)

    def live_sources(self) -> list[Source]:
        """Permission gate: only mentor-approved sources may be collected live."""
        return [s for s in self.sources if s.approval_status.upper() == "APPROVED"]


_REQUIRED_SOURCE = ("id", "company", "doc_type", "url", "refresh_hours", "selectors", "approval_status")


def load_config(path: str | Path) -> Settings:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ConfigError(f"config not found: {path}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    crawl = raw.get("crawl", {})
    s = Settings(
        user_agent=str(crawl.get("user_agent", "")).strip(),
        timeout=float(crawl.get("timeout_seconds", 15)),
        min_interval=float(crawl.get("min_interval_seconds", 10)),
        max_retries=int(crawl.get("max_retries", 3)),
        backoff_base=float(crawl.get("backoff_base_seconds", 2)),
        max_pages_per_run=int(crawl.get("max_pages_per_run", 10)),
        min_body_chars=int(crawl.get("min_body_chars", 200)),
    )
    if not s.user_agent:
        raise ConfigError("crawl.user_agent is required (descriptive User-Agent)")
    if s.timeout <= 0 or s.min_interval < 1 or s.max_retries < 0:
        raise ConfigError("timeout must be >0, min_interval >=1s, max_retries >=0")

    seen = set()
    for item in raw.get("sources", []):
        missing = [k for k in _REQUIRED_SOURCE if k not in item]
        if missing:
            raise ConfigError(f"source {item.get('id', '?')} missing keys: {missing}")
        if item["id"] in seen:
            raise ConfigError(f"duplicate source id: {item['id']}")
        seen.add(item["id"])
        if urlparse(item["url"]).scheme not in ("http", "https"):
            raise ConfigError(f"source {item['id']}: url must be http(s)")
        if int(item["refresh_hours"]) < 1:
            raise ConfigError(f"source {item['id']}: refresh_hours must be >= 1")
        if "body" not in item["selectors"]:
            raise ConfigError(f"source {item['id']}: selectors.body is required")
        s.sources.append(Source(
            id=item["id"], company=item["company"], doc_type=item["doc_type"],
            url=item["url"], refresh_hours=int(item["refresh_hours"]),
            selectors=item["selectors"], approval_status=str(item["approval_status"]),
            fixture=item.get("fixture"),
        ))
    return s
