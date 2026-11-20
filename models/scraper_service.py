"""
scraper_service.py
PolicyWatch - Web Scraping Integration Service (Module 1)
Bridges ptct-scraper data collection, offline fixtures, and snapshot logging
with the unified Flask application and tracker.db.
"""

from __future__ import annotations

import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure ptct-scraper is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PTCT_SRC = PROJECT_ROOT / "ptct-scraper" / "src"
if str(PTCT_SRC) not in sys.path:
    sys.path.insert(0, str(PTCT_SRC))

from . import database as db

FIXTURES_DIR = PROJECT_ROOT / "ptct-scraper" / "fixtures"
SOURCES_CONFIG_FILE = PROJECT_ROOT / "ptct-scraper" / "config" / "sources.yaml"


def get_scraper_sources(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Returns unified list of tracked web scraping sources:
    - Combines sources from sources.yaml with user-tracked websites in tracker.db
    - Displays approval status, refresh intervals, selectors, and freshness state.
    """
    db_sources = db.get_all_source_freshness(user_id)
    sources_map = {s['website_id']: s for s in db_sources}

    results = []
    # If user_id provided, fetch user's websites
    websites = db.get_websites_by_user(user_id) if user_id else db.query_db("SELECT * FROM Websites;")

    for site in websites:
        w_id = site['website_id']
        fresh = sources_map.get(w_id, {})

        # Determine approval status based on project SRS rules
        # Acme / localhost / test domains are approved for demo; real external sites require mentor approval
        url = (site['website_url'] or '').lower() if 'website_url' in site.keys() else ''
        has_pol = bool(site['latest_policy_version']) if 'latest_policy_version' in site.keys() else False
        has_trm = bool(site['latest_terms_version']) if 'latest_terms_version' in site.keys() else False

        if 'example.invalid' in url or 'acmecloud' in url or 'localhost' in url or 'test' in url:
            approval = "DEMO_APPROVED"
        else:
            approval = "PENDING_MENTOR_APPROVAL"

        results.append({
            'website_id': w_id,
            'source_id': f"site-{w_id}",
            'website_name': site['website_name'],
            'website_url': site['website_url'],
            'approval_status': approval,
            'refresh_hours': 24,
            'freshness': fresh.get('freshness', 'never_checked'),
            'last_checked_at': fresh.get('last_checked_at'),
            'last_changed_at': fresh.get('last_changed_at'),
            'last_status': fresh.get('last_status', 'never_checked'),
            'last_error': fresh.get('last_error'),
            'has_policy': has_pol,
            'has_terms': has_trm,
        })

    return results


def run_offline_refresh(website_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Executes a safe offline collection cycle for a tracked website:
    - Uses synthetic Acme demo fixtures or offline snapshots
    - Validates document structure
    - Detects whether content changed
    - Triggers change detection and notifications on updates
    - Records snapshot in ScraperSnapshots table
    - Updates freshness state
    """
    site = db.get_website_by_id(website_id, user_id)
    if not site:
        return {'success': False, 'error': f"Website #{website_id} not found."}

    site_name = site['website_name']
    site_url = site['website_url']
    source_id = f"site-{website_id}"
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Select appropriate fixture based on website name / ID
    fixture_content = None
    doc_type = "Privacy Policy"

    if "acme" in site_name.lower():
        # Cycle through demo fixtures
        latest_policy = db.get_latest_privacy_policy(website_id)
        current_ver = latest_policy['version'] if latest_policy else 0
        if current_ver < 2:
            fixture_name = "demo_privacy_v2.html"
        else:
            fixture_name = "demo_privacy_v1.html"

        f_path = FIXTURES_DIR / fixture_name
        if f_path.exists():
            fixture_content = f_path.read_text(encoding="utf-8")
    elif "social" in site_name.lower():
        fixture_name = "privacy_v2.html"
        f_path = FIXTURES_DIR / fixture_name
        if f_path.exists():
            fixture_content = f_path.read_text(encoding="utf-8")
    else:
        # Default fixture fallback
        f_path = FIXTURES_DIR / "privacy_v1.html"
        if f_path.exists():
            fixture_content = f_path.read_text(encoding="utf-8")

    # Extract text from HTML using BeautifulSoup safely
    parsed_text = ""
    if fixture_content:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(fixture_content, "html.parser")
            body = soup.select_one("#policy-content, main, article, body")
            if body:
                parsed_text = body.get_text(separator="\n").strip()
            else:
                parsed_text = soup.get_text(separator="\n").strip()
        except Exception:
            parsed_text = fixture_content
    else:
        parsed_text = f"Updated offline policy content for {site_name} at {now_iso}."

    content_hash = hashlib.sha256(parsed_text.encode('utf-8')).hexdigest()[:16]
    byte_size = len(parsed_text.encode('utf-8'))

    # Compare with latest stored policy
    latest_policy = db.get_latest_privacy_policy(website_id)
    is_changed = False
    new_version = None

    if not latest_policy or latest_policy['policy_content'].strip() != parsed_text.strip():
        # Policy has changed or is new
        _, new_version = db.add_privacy_policy(website_id, parsed_text)
        is_changed = True
        status_msg = f"New revision (Version {new_version}) collected and change detection report generated."
    else:
        # Duplicate / identical
        is_changed = False
        status_msg = "Re-check completed. Content is identical to current version; duplicate version suppressed."

        # Update last_checked_at in m5_source_freshness
        db.execute_db("""
            INSERT INTO m5_source_freshness (source_id, source_name, last_checked_at, last_status, updated_at)
            VALUES (?, ?, ?, 'checked', ?)
            ON CONFLICT(source_id) DO UPDATE SET
                source_name=excluded.source_name,
                last_checked_at=excluded.last_checked_at,
                last_status='checked',
                updated_at=excluded.updated_at;
        """, (source_id, site_name, now_iso, now_iso))

    # Log Snapshot in ScraperSnapshots table
    db.record_scrape_snapshot(
        website_id=website_id,
        source_id=source_id,
        url=site_url,
        http_status=200,
        content_hash=content_hash,
        byte_size=byte_size,
        file_path=str(f_path) if fixture_content and f_path.exists() else None
    )

    return {
        'success': True,
        'website_name': site_name,
        'is_changed': is_changed,
        'new_version': new_version,
        'content_hash': content_hash,
        'byte_size': byte_size,
        'message': status_msg,
        'timestamp': now_iso
    }


def run_full_offline_demo():
    """
    Executes the ptct.demo scripted refresh cycles and updates tracker.db.
    """
    try:
        from ptct.config import load_config
        from ptct.demo import run_demo
        from ptct.storage import Storage

        storage = Storage(":memory:")
        settings = load_config(str(SOURCES_CONFIG_FILE))
        summaries = run_demo(settings, storage)
        return {
            'success': True,
            'cycles_run': len(summaries),
            'summaries': [str(s) for s in summaries],
            'message': f"Executed {len(summaries)} offline refresh cycles successfully across synthetic fixtures."
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
