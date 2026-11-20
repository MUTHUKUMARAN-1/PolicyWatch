"""
server.py - PolicyWatch Standalone Authentication & Integration Server
Part of the PolicyWatch Project (DBMS, Change Detection, Scraper Integration)
Runs with standard Python 3 (ZERO external dependencies required).
"""

from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import json
import os
import sqlite3
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Resolve paths to PolicyWatch components
PORTAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PORTAL_DIR.parent / "PolicyWatch"
DB_PATH = PROJECT_ROOT / "models" / "tracker.db"
CHANGE_DETECTION_DIR = PROJECT_ROOT / "change_detection"
SCRAPER_DIR = PROJECT_ROOT / "ptct-scraper"

# Try importing change_detection module if available
sys.path.insert(0, str(PROJECT_ROOT))
try:
    from change_detection.api import detect_changes
    CHANGE_DETECTION_AVAILABLE = True
except Exception as e:
    detect_changes = None
    CHANGE_DETECTION_AVAILABLE = False


# ====================================================================
# PASSWORD HASHING & VERIFICATION (Compatible with Werkzeug / tracker.db)
# ====================================================================

def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies a password against scrypt or pbkdf2 stored in tracker.db."""
    if not stored_hash or not password:
        return False
    parts = stored_hash.split('$')
    if len(parts) != 3:
        # Fallback for plain text if any
        return stored_hash == password

    method_info, salt_str, hash_hex = parts[0], parts[1], parts[2]
    salt = salt_str.encode('utf-8')

    try:
        if method_info.startswith('scrypt:'):
            p_items = method_info.split(':')
            n, r, p = int(p_items[1]), int(p_items[2]), int(p_items[3])
            derived = hashlib.scrypt(
                password.encode('utf-8'),
                salt=salt,
                n=n,
                r=r,
                p=p,
                maxmem=64 * 1024 * 1024
            )
            return binascii.hexlify(derived).decode() == hash_hex
        elif method_info.startswith('pbkdf2:'):
            p_items = method_info.split(':')
            hash_name = p_items[1]
            iterations = int(p_items[2])
            derived = hashlib.pbkdf2_hmac(
                hash_name,
                password.encode('utf-8'),
                salt,
                iterations
            )
            return binascii.hexlify(derived).decode() == hash_hex
    except Exception as exc:
        print(f"[auth error] {exc}")
        return False

    return False


def hash_password(password: str) -> str:
    """Hashes a password using scrypt formatted identically to Werkzeug."""
    salt = binascii.hexlify(os.urandom(8)).decode('ascii')
    n, r, p = 32768, 8, 1
    derived = hashlib.scrypt(
        password.encode('utf-8'),
        salt=salt.encode('utf-8'),
        n=n,
        r=r,
        p=p,
        maxmem=64 * 1024 * 1024
    )
    hex_derived = binascii.hexlify(derived).decode('ascii')
    return f"scrypt:{n}:{r}:{p}${salt}${hex_derived}"


# ====================================================================
# DATABASE ACCESS HELPERS (DBMS - tracker.db)
# ====================================================================

def get_db_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_user_by_identifier(identifier: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM Users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE LIMIT 1;",
        (identifier.strip(), identifier.strip())
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_dashboard_data(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()

    # User basic info
    cur.execute("SELECT user_id, username, email, created_at FROM Users WHERE user_id = ?", (user_id,))
    user_row = cur.fetchone()
    if not user_row:
        conn.close()
        return None
    user = dict(user_row)

    # Websites owned by user
    cur.execute("""
        SELECT website_id, website_name, website_url, created_at
        FROM Websites
        WHERE user_id = ?
        ORDER BY website_id ASC
    """, (user_id,))
    websites = [dict(w) for w in cur.fetchall()]

    for w in websites:
        w_id = w['website_id']
        # Latest policy
        cur.execute("""
            SELECT policy_id, version, updated_at, policy_content
            FROM PrivacyPolicies
            WHERE website_id = ?
            ORDER BY version DESC LIMIT 1
        """, (w_id,))
        p_row = cur.fetchone()
        w['latest_policy'] = dict(p_row) if p_row else None

        # Latest terms
        cur.execute("""
            SELECT terms_id, version, updated_at, terms_content
            FROM TermsConditions
            WHERE website_id = ?
            ORDER BY version DESC LIMIT 1
        """, (w_id,))
        t_row = cur.fetchone()
        w['latest_terms'] = dict(t_row) if t_row else None

        # Version counts
        cur.execute("SELECT COUNT(*) AS cnt FROM PrivacyPolicies WHERE website_id = ?", (w_id,))
        w['policy_version_count'] = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM TermsConditions WHERE website_id = ?", (w_id,))
        w['terms_version_count'] = cur.fetchone()['cnt']

        # Recent changes for this website
        cur.execute("""
            SELECT change_id, change_type, old_version, new_version, change_date
            FROM ChangeHistory
            WHERE website_id = ?
            ORDER BY change_date DESC LIMIT 5
        """, (w_id,))
        w['recent_changes'] = [dict(c) for c in cur.fetchall()]

    # Global change history for this user
    cur.execute("""
        SELECT c.change_id, c.website_id, w.website_name, c.change_type,
               c.old_version, c.new_version, c.change_date
        FROM ChangeHistory c
        JOIN Websites w ON c.website_id = w.website_id
        WHERE w.user_id = ?
        ORDER BY c.change_date DESC LIMIT 20
    """, (user_id,))
    change_history = [dict(ch) for ch in cur.fetchall()]

    # Global metrics
    cur.execute("SELECT COUNT(*) AS cnt FROM Websites WHERE user_id = ?", (user_id,))
    total_sites = cur.fetchone()['cnt']

    cur.execute("""
        SELECT COUNT(*) AS cnt FROM PrivacyPolicies p
        JOIN Websites w ON p.website_id = w.website_id
        WHERE w.user_id = ?
    """, (user_id,))
    total_policies = cur.fetchone()['cnt']

    cur.execute("""
        SELECT COUNT(*) AS cnt FROM TermsConditions t
        JOIN Websites w ON t.website_id = w.website_id
        WHERE w.user_id = ?
    """, (user_id,))
    total_terms = cur.fetchone()['cnt']

    cur.execute("""
        SELECT COUNT(*) AS cnt FROM ChangeHistory c
        JOIN Websites w ON c.website_id = w.website_id
        WHERE w.user_id = ?
    """, (user_id,))
    total_changes = cur.fetchone()['cnt']

    conn.close()

    return {
        'user': user,
        'metrics': {
            'total_websites': total_sites,
            'total_policies': total_policies,
            'total_terms': total_terms,
            'total_versions': total_policies + total_terms,
            'total_changes': total_changes
        },
        'websites': websites,
        'change_history': change_history
    }


def get_all_website_versions(website_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Websites WHERE website_id = ?", (website_id,))
    site = cur.fetchone()
    if not site:
        conn.close()
        return None

    cur.execute("SELECT * FROM PrivacyPolicies WHERE website_id = ? ORDER BY version ASC", (website_id,))
    policies = [dict(p) for p in cur.fetchall()]

    cur.execute("SELECT * FROM TermsConditions WHERE website_id = ? ORDER BY version ASC", (website_id,))
    terms = [dict(t) for t in cur.fetchall()]

    cur.execute("SELECT * FROM ChangeHistory WHERE website_id = ? ORDER BY change_date DESC", (website_id,))
    history = [dict(h) for h in cur.fetchall()]

    conn.close()
    return {
        'website': dict(site),
        'policies': policies,
        'terms': terms,
        'history': history
    }


# ====================================================================
# SCRAPER DATA ACCESS (ptct-scraper evidence)
# ====================================================================

def get_scraper_evidence():
    exports_dir = SCRAPER_DIR / "docs" / "evidence" / "demo_run" / "exports"
    changes_file = exports_dir / "changes.csv"
    snapshots_file = exports_dir / "snapshots.csv"
    source_state_file = exports_dir / "source_state.csv"
    cases_file = SCRAPER_DIR / "docs" / "evidence" / "change_case_results.csv"

    def read_csv(path):
        if not path.exists():
            return []
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]

    return {
        'changes': read_csv(changes_file),
        'snapshots': read_csv(snapshots_file),
        'source_state': read_csv(source_state_file),
        'cases': read_csv(cases_file)
    }


# ====================================================================
# HTTP REQUEST HANDLER
# ====================================================================

class PolicyWatchHandler(BaseHTTPRequestHandler):
    server_version = "PolicyWatchAuth/2.0"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: any) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self._send(status, payload, "application/json; charset=utf-8")

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # Serve static HTML login page
        if path in ("/", "/login", "/login.html"):
            html_file = PORTAL_DIR / "login.html"
            if html_file.exists():
                self._send(200, html_file.read_bytes(), "text/html; charset=utf-8")
            else:
                self._json(404, {"error": "login.html not found"})
            return

        # System Status
        elif path == "/api/status":
            self._json(200, {
                "status": "online",
                "dbms": {
                    "database_path": str(DB_PATH),
                    "exists": DB_PATH.exists()
                },
                "change_detection": {
                    "available": CHANGE_DETECTION_AVAILABLE
                },
                "scraper": {
                    "exists": SCRAPER_DIR.exists()
                }
            })
            return

        # Quick accounts for viva demonstration
        elif path == "/api/demo-accounts":
            self._json(200, {
                "accounts": [
                    {
                        "role": "Administrator",
                        "username": "admin",
                        "password": "admin123",
                        "email": "admin@tracker.local",
                        "description": "Full access to 3 enterprise websites (Acme Cloud, SocialPulse, PaySwift) with multi-version GDPR/AI policy revisions."
                    },
                    {
                        "role": "Standard User",
                        "username": "john_doe",
                        "password": "password123",
                        "email": "john@example.com",
                        "description": "Standard user account monitoring DevPortal Community open-source terms."
                    }
                ]
            })
            return

        # User Dashboard Data
        elif path == "/api/dashboard":
            user_id = qs.get("user_id", [None])[0]
            if not user_id:
                self._json(400, {"error": "user_id is required"})
                return
            try:
                data = get_user_dashboard_data(int(user_id))
                if not data:
                    self._json(404, {"error": "User not found"})
                    return
                self._json(200, data)
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        # Full Versions for a specific Website
        elif path == "/api/website-versions":
            website_id = qs.get("website_id", [None])[0]
            if not website_id:
                self._json(400, {"error": "website_id is required"})
                return
            try:
                data = get_all_website_versions(int(website_id))
                if not data:
                    self._json(404, {"error": "Website not found"})
                    return
                self._json(200, data)
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        # Scraper Evidence Data
        elif path == "/api/scraper-feed":
            try:
                evidence = get_scraper_evidence()
                self._json(200, evidence)
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        else:
            self._json(404, {"error": f"Unknown endpoint: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except Exception:
            self._json(400, {"error": "Invalid JSON body"})
            return

        # User Login
        if path == "/api/login":
            identifier = body.get("identifier", "").strip()
            password = body.get("password", "")

            if not identifier or not password:
                self._json(400, {"error": "Username/Email and Password are required."})
                return

            user = get_user_by_identifier(identifier)
            if not user:
                self._json(401, {"error": "Invalid username/email or password."})
                return

            if verify_password(user["password"], password):
                dashboard_data = get_user_dashboard_data(user["user_id"])
                self._json(200, {
                    "success": True,
                    "message": f"Welcome back, {user['username']}!",
                    "user": {
                        "user_id": user["user_id"],
                        "username": user["username"],
                        "email": user["email"],
                        "created_at": user["created_at"]
                    },
                    "dashboard": dashboard_data
                })
            else:
                self._json(401, {"error": "Invalid username/email or password."})
            return

        # User Registration
        elif path == "/api/register":
            username = body.get("username", "").strip()
            email = body.get("email", "").strip().lower()
            password = body.get("password", "")
            confirm_password = body.get("confirm_password", "")

            # Validation
            if not username or len(username) < 3:
                self._json(400, {"error": "Username must be at least 3 characters long."})
                return
            if not email or "@" not in email or "." not in email:
                self._json(400, {"error": "Please provide a valid email address."})
                return
            if not password or len(password) < 6:
                self._json(400, {"error": "Password must be at least 6 characters long."})
                return
            if password != confirm_password:
                self._json(400, {"error": "Passwords do not match."})
                return

            # Check uniqueness
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM Users WHERE username = ? COLLATE NOCASE", (username,))
            if cur.fetchone():
                conn.close()
                self._json(400, {"error": "Username is already registered. Please choose another."})
                return

            cur.execute("SELECT user_id FROM Users WHERE email = ? COLLATE NOCASE", (email,))
            if cur.fetchone():
                conn.close()
                self._json(400, {"error": "An account with this email already exists."})
                return

            # Hash and save
            hashed = hash_password(password)
            cur.execute(
                "INSERT INTO Users (username, email, password) VALUES (?, ?, ?)",
                (username, email, hashed)
            )
            new_user_id = cur.lastrowid
            conn.commit()
            conn.close()

            dashboard_data = get_user_dashboard_data(new_user_id)
            self._json(201, {
                "success": True,
                "message": "Account created successfully!",
                "user": {
                    "user_id": new_user_id,
                    "username": username,
                    "email": email
                },
                "dashboard": dashboard_data
            })
            return

        # Change Detection Comparison Endpoint
        elif path == "/api/compare":
            old_text = body.get("old_text", "")
            new_text = body.get("new_text", "")
            doc_id = body.get("doc_id", "policy-diff")

            if CHANGE_DETECTION_AVAILABLE and detect_changes is not None:
                try:
                    report = detect_changes(old_text, new_text, document_id=doc_id)
                    self._json(200, {
                        "engine": "PolicyWatch Semantic Change Detection",
                        "report": report.to_dict()
                    })
                    return
                except Exception as e:
                    print(f"[change detection error] {e}")

            # Fallback pure python diff if module import fails
            import difflib
            s = difflib.SequenceMatcher(None, old_text.splitlines(), new_text.splitlines())
            additions = sum(j2 - j1 for tag, i1, i2, j1, j2 in s.get_opcodes() if tag in ('replace', 'insert'))
            deletions = sum(i2 - i1 for tag, i1, i2, j1, j2 in s.get_opcodes() if tag in ('replace', 'delete'))
            self._json(200, {
                "engine": "difflib fallback",
                "report": {
                    "additions": additions,
                    "deletions": deletions,
                    "changes": []
                }
            })
            return

        else:
            self._json(404, {"error": f"Unknown POST endpoint: {path}"})

    def log_message(self, fmt, *args):
        # Concise logging
        print(f"[PolicyWatch-Auth] {args[0]} -> {args[1]}")


# ====================================================================
# ENTRYPOINT
# ====================================================================

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PolicyWatch Authentication & User Portal Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5050, help="Port to listen on (default: 5050)")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("🔒 POLICYWATCH: USER AUTHENTICATION & CHANGE TRACKER PORTAL")
    print("=" * 70)
    print(f"[*] DBMS Database:          {DB_PATH} ({'FOUND' if DB_PATH.exists() else 'NOT FOUND'})")
    print(f"[*] Change Detection Core:  {'ACTIVE' if CHANGE_DETECTION_AVAILABLE else 'OFFLINE (FALLBACK)'}")
    print(f"[*] Web Scraper Feed:       {SCRAPER_DIR} ({'CONNECTED' if SCRAPER_DIR.exists() else 'OFFLINE'})")
    print(f"[*] Server URL:             http://localhost:{args.port}/")
    print(f"[*] Demo Accounts:          Admin ('admin' / 'admin123') | User ('john_doe' / 'password123')")
    print("=" * 70)
    print(f"Serving login interface at http://localhost:{args.port}/  (Press Ctrl+C to stop)")

    httpd = ThreadingHTTPServer((args.host, args.port), PolicyWatchHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down server gracefully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
