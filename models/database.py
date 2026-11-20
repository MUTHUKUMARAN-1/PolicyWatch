"""
database.py
PolicyWatch - Unified Database Access Layer
Supports:
- Module 1: Scraper Snapshots & Source State
- Module 2: Relational DBMS Core (Users, Websites, Policies, Terms, ChangeHistory)
- Module 3: Authentication & Profile Data
- Module 4: Search, Multi-Criteria Filtering, and Change Details
- Module 5: Notifications & Freshness Tracking
"""

import os
import sqlite3
import json
from datetime import datetime, timezone
from flask import g, has_app_context

DATABASE_FILE = os.environ.get(
    "POLICYWATCH_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.db")
)

os.makedirs(os.path.dirname(os.path.abspath(DATABASE_FILE)), exist_ok=True)

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

def get_db():
    """
    Returns the database connection.
    If within a Flask application context, reuses g.db;
    otherwise opens and returns a standalone connection.
    Configures foreign keys and Row factory.
    """
    if has_app_context():
        if 'db' not in g:
            g.db = sqlite3.connect(DATABASE_FILE)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON;")
            ensure_schema_upgrades(g.db)
        return g.db
    else:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        ensure_schema_upgrades(conn)
        return conn


def close_db(e=None):
    """
    Closes the database connection at the end of the request.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def ensure_schema_upgrades(conn=None):
    """
    Safely applies backwards-compatible schema upgrades to existing databases.
    Ensures Module 4, Module 5, and Scraper columns exist.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    try:
        cur = conn.cursor()

        # Check ChangeHistory columns
        cur.execute("PRAGMA table_info(ChangeHistory);")
        existing_cols = {row['name'] if isinstance(row, sqlite3.Row) else row[1] for row in cur.fetchall()}

        columns_to_add = [
            ('summary', 'TEXT'),
            ('category', "TEXT DEFAULT 'general'"),
            ('severity', "TEXT DEFAULT 'moderate'"),
            ('reasons', 'TEXT'),
            ('review_status', "TEXT DEFAULT 'unreviewed'"),
            ('reviewed_by', 'TEXT'),
            ('review_notes', 'TEXT'),
            ('diff_json', 'TEXT')
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_cols:
                try:
                    cur.execute(f"ALTER TABLE ChangeHistory ADD COLUMN {col_name} {col_type};")
                except Exception:
                    pass

        # Ensure Module 5 and Scraper tables exist
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS m5_source_freshness (
                source_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                last_checked_at TEXT,
                last_changed_at TEXT,
                last_status TEXT NOT NULL DEFAULT 'never_checked',
                last_error TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS m5_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                website_id INTEGER,
                change_id INTEGER,
                FOREIGN KEY(source_id) REFERENCES m5_source_freshness(source_id) ON DELETE CASCADE,
                FOREIGN KEY(website_id) REFERENCES Websites(website_id) ON DELETE CASCADE,
                FOREIGN KEY(change_id) REFERENCES ChangeHistory(change_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS ScraperSnapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                website_id INTEGER,
                source_id TEXT NOT NULL,
                url TEXT NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                http_status INTEGER DEFAULT 200,
                content_hash TEXT,
                byte_size INTEGER DEFAULT 0,
                file_path TEXT,
                FOREIGN KEY(website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    finally:
        if should_close:
            conn.close()


def init_db(db_path=None):
    """
    Initializes the database using schema.sql.
    Can be run standalone or from the Flask CLI.
    """
    target_path = db_path or DATABASE_FILE
    conn = sqlite3.connect(target_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[OK] Database initialized successfully at: {target_path}")


def query_db(query, args=(), one=False):
    """
    Helper function to execute SELECT queries and return rows.
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=(), commit=True):
    """
    Helper function to execute INSERT, UPDATE, DELETE queries.
    Returns the lastrowid of inserted records.
    """
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


# ====================================================================
# USER CRUD OPERATIONS (Module 3)
# ====================================================================

def create_user(username, email, password_hash):
    """
    Registers a new user into the Users table.
    """
    query = """
        INSERT INTO Users (username, email, password)
        VALUES (?, ?, ?);
    """
    return execute_db(query, (username.strip(), email.strip().lower(), password_hash))


def get_user_by_username(username):
    """
    Retrieves user record by username (case-insensitive).
    """
    query = "SELECT * FROM Users WHERE username = ? COLLATE NOCASE;"
    return query_db(query, (username.strip(),), one=True)


def get_user_by_email(email):
    """
    Retrieves user record by email (case-insensitive).
    """
    query = "SELECT * FROM Users WHERE email = ? COLLATE NOCASE;"
    return query_db(query, (email.strip().lower(),), one=True)


def get_user_by_id(user_id):
    """
    Retrieves user record by user_id.
    """
    query = "SELECT * FROM Users WHERE user_id = ?;"
    return query_db(query, (user_id,), one=True)


# ====================================================================
# WEBSITE CRUD OPERATIONS (Module 2)
# ====================================================================

def create_website(user_id, website_name, website_url, domain=None):
    """
    Adds a new website tracked by the user.
    Also initializes source freshness tracking in Module 5.
    """
    query = """
        INSERT INTO Websites (user_id, website_name, website_url)
        VALUES (?, ?, ?);
    """
    site_id = execute_db(query, (user_id, website_name.strip(), website_url.strip()))

    # Initialize freshness record in m5_source_freshness
    source_id = f"site-{site_id}"
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    execute_db("""
        INSERT OR IGNORE INTO m5_source_freshness
        (source_id, source_name, last_status, updated_at)
        VALUES (?, ?, 'never_checked', ?);
    """, (source_id, website_name.strip(), now_iso))

    return site_id


add_website = create_website


def get_websites_by_user(user_id, search_query=None):
    """
    Lists all websites belonging to a user, with optional search filter.
    Includes latest policy version and terms version using subqueries.
    """
    if search_query:
        query = """
            SELECT w.*,
                   (SELECT MAX(version) FROM PrivacyPolicies WHERE website_id = w.website_id) AS latest_policy_version,
                   (SELECT MAX(updated_at) FROM PrivacyPolicies WHERE website_id = w.website_id) AS last_policy_update,
                   (SELECT MAX(version) FROM TermsConditions WHERE website_id = w.website_id) AS latest_terms_version,
                   (SELECT MAX(updated_at) FROM TermsConditions WHERE website_id = w.website_id) AS last_terms_update
            FROM Websites w
            WHERE w.user_id = ? AND (w.website_name LIKE ? OR w.website_url LIKE ?)
            ORDER BY w.created_at DESC;
        """
        pattern = f"%{search_query.strip()}%"
        return query_db(query, (user_id, pattern, pattern))
    else:
        query = """
            SELECT w.*,
                   (SELECT MAX(version) FROM PrivacyPolicies WHERE website_id = w.website_id) AS latest_policy_version,
                   (SELECT MAX(updated_at) FROM PrivacyPolicies WHERE website_id = w.website_id) AS last_policy_update,
                   (SELECT MAX(version) FROM TermsConditions WHERE website_id = w.website_id) AS latest_terms_version,
                   (SELECT MAX(updated_at) FROM TermsConditions WHERE website_id = w.website_id) AS last_terms_update
            FROM Websites w
            WHERE w.user_id = ?
            ORDER BY w.created_at DESC;
        """
        return query_db(query, (user_id,))


def get_website_by_id(website_id, user_id=None):
    """
    Retrieves a single website. If user_id is provided, enforces ownership check.
    """
    if user_id is not None:
        query = "SELECT * FROM Websites WHERE website_id = ? AND user_id = ?;"
        return query_db(query, (website_id, user_id), one=True)
    else:
        query = "SELECT * FROM Websites WHERE website_id = ?;"
        return query_db(query, (website_id,), one=True)


def update_website(website_id, user_id, website_name, website_url):
    """
    Updates the name and URL of a tracked website.
    """
    query = """
        UPDATE Websites
        SET website_name = ?, website_url = ?
        WHERE website_id = ? AND user_id = ?;
    """
    execute_db(query, (website_name.strip(), website_url.strip(), website_id, user_id))


def delete_website(website_id, user_id):
    """
    Deletes a website. Due to ON DELETE CASCADE, all associated
    policies, terms, change history, and notifications are deleted.
    """
    query = "DELETE FROM Websites WHERE website_id = ? AND user_id = ?;"
    execute_db(query, (website_id, user_id))


# ====================================================================
# PRIVACY POLICY & TERMS TRACKING (CRUD & VERSIONING)
# ====================================================================

def get_latest_privacy_policy(website_id):
    """
    Retrieves the most recent version of the Privacy Policy for a website.
    """
    query = """
        SELECT * FROM PrivacyPolicies
        WHERE website_id = ?
        ORDER BY version DESC
        LIMIT 1;
    """
    return query_db(query, (website_id,), one=True)


def get_privacy_policy_by_version(website_id, version):
    """
    Retrieves a specific version of a website's Privacy Policy.
    """
    query = """
        SELECT * FROM PrivacyPolicies
        WHERE website_id = ? AND version = ?;
    """
    return query_db(query, (website_id, version), one=True)


def get_privacy_policy_history(website_id):
    """
    Lists all stored versions of a website's Privacy Policy in descending order.
    """
    query = """
        SELECT * FROM PrivacyPolicies
        WHERE website_id = ?
        ORDER BY version DESC;
    """
    return query_db(query, (website_id,))


def add_privacy_policy(website_id, policy_content):
    """
    Saves a new version of the Privacy Policy.
    Automatically increments version number, classifies changes using
    change_detection module, records in ChangeHistory, and fires notification.
    """
    latest = get_latest_privacy_policy(website_id)
    if latest:
        old_version = latest['version']
        new_version = old_version + 1
        old_content = latest['policy_content']
    else:
        old_version = None
        new_version = 1
        old_content = ""

    query = """
        INSERT INTO PrivacyPolicies (website_id, policy_content, version)
        VALUES (?, ?, ?);
    """
    policy_id = execute_db(query, (website_id, policy_content.strip(), new_version))

    # Automatic Change Classification using change_detection
    summary = f"Privacy Policy updated to Version {new_version}."
    category = "general"
    severity = "minor" if old_version is None else "moderate"
    reasons = ""

    if old_content and old_content != policy_content:
        try:
            from change_detection.api import detect_changes
            report = detect_changes(old_content, policy_content, document_id=f"site_{website_id}_privacy")
            if report.changes:
                top_change = report.changes[0]
                category = top_change.category or "general"
                severity = top_change.severity or "moderate"
                reasons = "; ".join(top_change.reasons) if top_change.reasons else ""
                summary = top_change.title or f"{len(report.changes)} clause modifications detected."
        except Exception:
            pass

    # Record in ChangeHistory table
    change_id = record_change(
        website_id=website_id,
        change_type='Privacy Policy',
        old_version=old_version,
        new_version=new_version,
        summary=summary,
        category=category,
        severity=severity,
        reasons=reasons
    )

    # Update Freshness & Trigger Notification in Module 5
    site = get_website_by_id(website_id)
    site_name = site['website_name'] if site else f"Website #{website_id}"
    source_id = f"site-{website_id}"
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    execute_db("""
        INSERT INTO m5_source_freshness (source_id, source_name, last_checked_at, last_changed_at, last_status, updated_at)
        VALUES (?, ?, ?, ?, 'changed', ?)
        ON CONFLICT(source_id) DO UPDATE SET
            source_name=excluded.source_name,
            last_checked_at=excluded.last_checked_at,
            last_changed_at=excluded.last_changed_at,
            last_status='changed',
            updated_at=excluded.updated_at;
    """, (source_id, site_name, now_iso, now_iso, now_iso))

    execute_db("""
        INSERT INTO m5_notifications (source_id, source_name, notification_type, title, message, created_at, website_id, change_id)
        VALUES (?, ?, 'policy_changed', ?, ?, ?, ?, ?);
    """, (source_id, site_name, f"Privacy Policy Updated: {site_name}", summary, now_iso, website_id, change_id))

    return policy_id, new_version


def delete_privacy_policy_version(policy_id, website_id):
    """
    Deletes a single privacy policy version.
    """
    query = "DELETE FROM PrivacyPolicies WHERE policy_id = ? AND website_id = ?;"
    execute_db(query, (policy_id, website_id))


def get_latest_terms_conditions(website_id):
    """
    Retrieves the most recent version of Terms & Conditions for a website.
    """
    query = """
        SELECT * FROM TermsConditions
        WHERE website_id = ?
        ORDER BY version DESC
        LIMIT 1;
    """
    return query_db(query, (website_id,), one=True)


def get_terms_by_version(website_id, version):
    """
    Retrieves a specific version of a website's Terms & Conditions.
    """
    query = """
        SELECT * FROM TermsConditions
        WHERE website_id = ? AND version = ?;
    """
    return query_db(query, (website_id, version), one=True)


def get_terms_history(website_id):
    """
    Lists all stored versions of a website's Terms & Conditions in descending order.
    """
    query = """
        SELECT * FROM TermsConditions
        WHERE website_id = ?
        ORDER BY version DESC;
    """
    return query_db(query, (website_id,))


def add_terms_conditions(website_id, terms_content):
    """
    Saves a new version of the Terms & Conditions.
    Automatically increments version number, classifies changes using
    change_detection module, records in ChangeHistory, and fires notification.
    """
    latest = get_latest_terms_conditions(website_id)
    if latest:
        old_version = latest['version']
        new_version = old_version + 1
        old_content = latest['terms_content']
    else:
        old_version = None
        new_version = 1
        old_content = ""

    query = """
        INSERT INTO TermsConditions (website_id, terms_content, version)
        VALUES (?, ?, ?);
    """
    terms_id = execute_db(query, (website_id, terms_content.strip(), new_version))

    # Automatic Change Classification using change_detection
    summary = f"Terms & Conditions updated to Version {new_version}."
    category = "general"
    severity = "minor" if old_version is None else "moderate"
    reasons = ""

    if old_content and old_content != terms_content:
        try:
            from change_detection.api import detect_changes
            report = detect_changes(old_content, terms_content, document_id=f"site_{website_id}_terms")
            if report.changes:
                top_change = report.changes[0]
                category = top_change.category or "general"
                severity = top_change.severity or "moderate"
                reasons = "; ".join(top_change.reasons) if top_change.reasons else ""
                summary = top_change.title or f"{len(report.changes)} clause modifications detected."
        except Exception:
            pass

    # Record in ChangeHistory table
    change_id = record_change(
        website_id=website_id,
        change_type='Terms & Conditions',
        old_version=old_version,
        new_version=new_version,
        summary=summary,
        category=category,
        severity=severity,
        reasons=reasons
    )

    # Update Freshness & Trigger Notification in Module 5
    site = get_website_by_id(website_id)
    site_name = site['website_name'] if site else f"Website #{website_id}"
    source_id = f"site-{website_id}"
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    execute_db("""
        INSERT INTO m5_source_freshness (source_id, source_name, last_checked_at, last_changed_at, last_status, updated_at)
        VALUES (?, ?, ?, ?, 'changed', ?)
        ON CONFLICT(source_id) DO UPDATE SET
            source_name=excluded.source_name,
            last_checked_at=excluded.last_checked_at,
            last_changed_at=excluded.last_changed_at,
            last_status='changed',
            updated_at=excluded.updated_at;
    """, (source_id, site_name, now_iso, now_iso, now_iso))

    execute_db("""
        INSERT INTO m5_notifications (source_id, source_name, notification_type, title, message, created_at, website_id, change_id)
        VALUES (?, ?, 'policy_changed', ?, ?, ?, ?, ?);
    """, (source_id, site_name, f"Terms & Conditions Updated: {site_name}", summary, now_iso, website_id, change_id))

    return terms_id, new_version


def delete_terms_version(terms_id, website_id):
    """
    Deletes a single terms version.
    """
    query = "DELETE FROM TermsConditions WHERE terms_id = ? AND website_id = ?;"
    execute_db(query, (terms_id, website_id))


# ====================================================================
# CHANGE HISTORY MANAGEMENT & AUDIT LOG (Module 2 & 4)
# ====================================================================

def record_change(website_id, change_type, old_version, new_version,
                  summary=None, category='general', severity='moderate',
                  reasons=None, review_status='unreviewed', diff_json=None):
    """
    Inserts an audit record into ChangeHistory with classification details.
    """
    query = """
        INSERT INTO ChangeHistory
        (website_id, change_type, old_version, new_version, summary, category, severity, reasons, review_status, diff_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    return execute_db(query, (
        website_id, change_type, old_version, new_version,
        summary, category, severity, reasons, review_status, diff_json
    ))


def get_change_history_for_website(website_id):
    """
    Returns the complete change history for a specific website.
    """
    query = """
        SELECT ch.*, w.website_name
        FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE ch.website_id = ?
        ORDER BY ch.change_date DESC, ch.change_id DESC;
    """
    return query_db(query, (website_id,))


get_changes_by_website = get_change_history_for_website


def get_all_change_history(user_id, limit=50):
    """
    Returns full change history across all websites owned by the user.
    """
    query = """
        SELECT ch.*, w.website_name, w.website_url
        FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE w.user_id = ?
        ORDER BY ch.change_date DESC, ch.change_id DESC
        LIMIT ?;
    """
    return query_db(query, (user_id, limit))


def get_change_by_id(change_id, user_id=None):
    """
    Retrieves full details for a single change record.
    If user_id is provided, verifies ownership.
    """
    if user_id is not None:
        query = """
            SELECT ch.*, w.website_name, w.website_url, w.user_id
            FROM ChangeHistory ch
            JOIN Websites w ON ch.website_id = w.website_id
            WHERE ch.change_id = ? AND w.user_id = ?;
        """
        return query_db(query, (change_id, user_id), one=True)
    else:
        query = """
            SELECT ch.*, w.website_name, w.website_url, w.user_id
            FROM ChangeHistory ch
            JOIN Websites w ON ch.website_id = w.website_id
            WHERE ch.change_id = ?;
        """
        return query_db(query, (change_id,), one=True)


def update_change_review_status(change_id, review_status, reviewed_by=None, review_notes=None):
    """
    Updates the human review status for a detected change (confirmed / rejected).
    """
    query = """
        UPDATE ChangeHistory
        SET review_status = ?, reviewed_by = ?, review_notes = ?
        WHERE change_id = ?;
    """
    execute_db(query, (review_status, reviewed_by, review_notes, change_id))


# ====================================================================
# MODULE 4: SEARCH & MULTI-CRITERIA FILTERING ENGINE
# ====================================================================

def search_records(user_id, query_str=None, site_id=None, doc_type=None,
                   severity=None, category=None, change_type=None,
                   review_status=None, date_from=None, date_to=None):
    """
    Unified multi-criteria search and filter engine across:
    - Websites (name, URL)
    - PrivacyPolicies and TermsConditions (full text)
    - ChangeHistory (summary, reasons, category, severity, review_status)
    """
    conditions = ["w.user_id = ?"]
    params = [user_id]

    if site_id:
        conditions.append("ch.website_id = ?")
        params.append(site_id)

    if change_type and change_type != 'all':
        conditions.append("ch.change_type = ?")
        params.append(change_type)

    if severity and severity != 'all':
        conditions.append("LOWER(ch.severity) = LOWER(?)")
        params.append(severity)

    if category and category != 'all':
        conditions.append("LOWER(ch.category) = LOWER(?)")
        params.append(category)

    if review_status and review_status != 'all':
        conditions.append("LOWER(ch.review_status) = LOWER(?)")
        params.append(review_status)

    if date_from:
        conditions.append("ch.change_date >= ?")
        params.append(f"{date_from} 00:00:00")

    if date_to:
        conditions.append("ch.change_date <= ?")
        params.append(f"{date_to} 23:59:59")

    if query_str:
        q_clean = query_str.strip()
        q_pattern = f"%{q_clean}%"
        search_clause = """(
            w.website_name LIKE ? OR
            w.website_url LIKE ? OR
            ch.summary LIKE ? OR
            ch.reasons LIKE ? OR
            ch.category LIKE ? OR
            EXISTS (SELECT 1 FROM PrivacyPolicies pp WHERE pp.website_id = w.website_id AND pp.policy_content LIKE ?) OR
            EXISTS (SELECT 1 FROM TermsConditions tc WHERE tc.website_id = w.website_id AND tc.terms_content LIKE ?)
        )"""
        conditions.append(search_clause)
        params.extend([q_pattern, q_pattern, q_pattern, q_pattern, q_pattern, q_pattern, q_pattern])

    where_sql = " AND ".join(conditions)

    query = f"""
        SELECT ch.*, w.website_name, w.website_url
        FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE {where_sql}
        ORDER BY ch.change_date DESC;
    """

    results = query_db(query, tuple(params))

    # Also search directly matching websites if a text query was provided
    matching_sites = []
    if query_str:
        s_pattern = f"%{query_str.strip()}%"
        site_query = """
            SELECT w.*
            FROM Websites w
            WHERE w.user_id = ? AND (w.website_name LIKE ? OR w.website_url LIKE ?)
            ORDER BY w.website_name ASC;
        """
        matching_sites = query_db(site_query, (user_id, s_pattern, s_pattern))

    return {
        'changes': results,
        'matching_sites': matching_sites,
        'count': len(results) + len(matching_sites)
    }


def get_distinct_categories():
    """Returns all unique category strings currently in ChangeHistory."""
    rows = query_db("SELECT DISTINCT category FROM ChangeHistory WHERE category IS NOT NULL AND category != '';")
    categories = sorted(list({r['category'] for r in rows}))
    if not categories:
        categories = ['data_collection', 'data_retention', 'third_party_sharing', 'user_rights', 'dispute_arbitration', 'security', 'general']
    return categories


def get_distinct_severities():
    """Returns supported severity levels."""
    return ['critical', 'major', 'moderate', 'minor', 'cosmetic']


# ====================================================================
# MODULE 5: NOTIFICATIONS & FRESHNESS TRACKING (tracker.db integration)
# ====================================================================

def get_notifications_for_user(user_id, unread_only=False, limit=50):
    """
    Returns notifications for websites tracked by the user.
    """
    if unread_only:
        query = """
            SELECT n.id AS notification_id, n.*, w.website_name, w.website_id
            FROM m5_notifications n
            LEFT JOIN Websites w ON n.website_id = w.website_id
            WHERE (w.user_id = ? OR n.website_id IS NULL) AND n.is_read = 0
            ORDER BY n.created_at DESC, n.id DESC
            LIMIT ?;
        """
    else:
        query = """
            SELECT n.id AS notification_id, n.*, w.website_name, w.website_id
            FROM m5_notifications n
            LEFT JOIN Websites w ON n.website_id = w.website_id
            WHERE (w.user_id = ? OR n.website_id IS NULL)
            ORDER BY n.created_at DESC, n.id DESC
            LIMIT ?;
        """
    return query_db(query, (user_id, limit))


def get_unread_notifications_count(user_id):
    """
    Counts unread notifications for the user.
    """
    query = """
        SELECT COUNT(*) AS cnt
        FROM m5_notifications n
        LEFT JOIN Websites w ON n.website_id = w.website_id
        WHERE (w.user_id = ? OR n.website_id IS NULL) AND n.is_read = 0;
    """
    row = query_db(query, (user_id,), one=True)
    return row['cnt'] if row else 0


# Backwards compatibility alias
get_unread_notification_count = get_unread_notifications_count


def mark_notification_as_read(notification_id):
    """
    Marks a notification as read.
    """
    query = "UPDATE m5_notifications SET is_read = 1 WHERE id = ?;"
    return execute_db(query, (notification_id,)) > 0


def mark_all_notifications_as_read(user_id):
    """
    Marks all notifications for the user as read.
    """
    query = """
        UPDATE m5_notifications
        SET is_read = 1
        WHERE is_read = 0 AND (website_id IN (SELECT website_id FROM Websites WHERE user_id = ?) OR website_id IS NULL);
    """
    return execute_db(query, (user_id,))


def get_freshness_status_for_source(last_checked_at):
    """
    Computes freshness string:
    - 'never_checked'
    - 'fresh' (< 24h)
    - 'aging' (24h - 72h)
    - 'stale' (> 72h)
    """
    if not last_checked_at:
        return 'never_checked'
    try:
        if isinstance(last_checked_at, str):
            # parse ISO or standard format
            clean_str = last_checked_at.replace("Z", "+00:00")
            if "T" in clean_str:
                dt = datetime.fromisoformat(clean_str)
            else:
                dt = datetime.strptime(clean_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            dt = last_checked_at
        age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
        if age_hours >= 72.0:
            return 'stale'
        elif age_hours >= 24.0:
            return 'aging'
        else:
            return 'fresh'
    except Exception:
        return 'fresh'


def get_all_source_freshness(user_id=None):
    """
    Returns freshness status for all tracked sources.
    """
    if user_id:
        query = """
            SELECT w.website_id, w.website_name, w.website_url,
                   f.source_id, f.last_checked_at, f.last_changed_at, f.last_status, f.last_error
            FROM Websites w
            LEFT JOIN m5_source_freshness f ON f.source_id = ('site-' || w.website_id)
            WHERE w.user_id = ?
            ORDER BY w.website_name ASC;
        """
        rows = query_db(query, (user_id,))
    else:
        query = """
            SELECT w.website_id, w.website_name, w.website_url,
                   f.source_id, f.last_checked_at, f.last_changed_at, f.last_status, f.last_error
            FROM Websites w
            LEFT JOIN m5_source_freshness f ON f.source_id = ('site-' || w.website_id)
            ORDER BY w.website_name ASC;
        """
        rows = query_db(query)

    result = []
    for r in rows:
        item = dict(r)
        item['freshness'] = get_freshness_status_for_source(item.get('last_checked_at'))
        result.append(item)
    return result


def get_freshness_summary(user_id=None):
    """
    Aggregates freshness metrics: {total, fresh, aging, stale, never_checked}.
    """
    all_fresh = get_all_source_freshness(user_id)
    summary = {'total': len(all_fresh), 'fresh': 0, 'aging': 0, 'stale': 0, 'never_checked': 0}
    for item in all_fresh:
        f = item.get('freshness', 'never_checked')
        summary[f] = summary.get(f, 0) + 1
    return summary


# ====================================================================
# MODULE 1: SCRAPER INTEGRATION HELPERS
# ====================================================================

def record_scrape_snapshot(website_id, source_id, url, http_status=200, content_hash=None, byte_size=0, file_path=None):
    """
    Logs an official scraper snapshot record.
    """
    query = """
        INSERT INTO ScraperSnapshots (website_id, source_id, url, http_status, content_hash, byte_size, file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    return execute_db(query, (website_id, source_id, url, http_status, content_hash, byte_size, file_path))


def get_recent_snapshots(website_id=None, limit=20):
    """
    Returns recent scraping snapshot records.
    """
    if website_id:
        query = """
            SELECT s.*, w.website_name
            FROM ScraperSnapshots s
            LEFT JOIN Websites w ON s.website_id = w.website_id
            WHERE s.website_id = ?
            ORDER BY s.fetched_at DESC LIMIT ?;
        """
        return query_db(query, (website_id, limit))
    else:
        query = """
            SELECT s.*, w.website_name
            FROM ScraperSnapshots s
            LEFT JOIN Websites w ON s.website_id = w.website_id
            ORDER BY s.fetched_at DESC LIMIT ?;
        """
        return query_db(query, (limit,))


# ====================================================================
# DASHBOARD METRICS & RECENT ACTIVITY
# ====================================================================

def get_dashboard_stats(user_id):
    """
    Aggregates comprehensive dashboard metrics for the logged-in user:
    - Total websites tracked
    - Total policy versions
    - Total terms versions
    - Total recorded changes
    - Critical / Major changes count
    - Unread notifications count
    - Freshness breakdown
    - Recently updated websites list
    """
    db = get_db()

    # 1. Total websites
    c_web = db.execute("SELECT COUNT(*) FROM Websites WHERE user_id = ?;", (user_id,)).fetchone()
    total_websites = c_web[0] if c_web else 0

    # 2. Total policy versions
    c_pol = db.execute("""
        SELECT COUNT(*) FROM PrivacyPolicies p
        JOIN Websites w ON p.website_id = w.website_id
        WHERE w.user_id = ?;
    """, (user_id,)).fetchone()
    total_policies = c_pol[0] if c_pol else 0

    # 3. Total terms versions
    c_term = db.execute("""
        SELECT COUNT(*) FROM TermsConditions t
        JOIN Websites w ON t.website_id = w.website_id
        WHERE w.user_id = ?;
    """, (user_id,)).fetchone()
    total_terms = c_term[0] if c_term else 0

    # 4. Total recorded changes
    c_hist = db.execute("""
        SELECT COUNT(*) FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE w.user_id = ?;
    """, (user_id,)).fetchone()
    total_changes = c_hist[0] if c_hist else 0

    # 5. Major & Critical changes
    c_crit = db.execute("""
        SELECT COUNT(*) FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE w.user_id = ? AND LOWER(ch.severity) IN ('critical', 'major');
    """, (user_id,)).fetchone()
    major_changes = c_crit[0] if c_crit else 0

    # 6. Unread notifications
    unread_notifications = get_unread_notifications_count(user_id)

    # 7. Freshness summary
    freshness = get_freshness_summary(user_id)

    # 8. Recently updated websites
    recent_updates = db.execute("""
        SELECT ch.change_id, ch.change_type, ch.old_version, ch.new_version, ch.change_date,
               ch.summary, ch.category, ch.severity, ch.review_status,
               w.website_id, w.website_name, w.website_url
        FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE w.user_id = ?
        ORDER BY ch.change_date DESC
        LIMIT 6;
    """, (user_id,)).fetchall()

    return {
        'total_websites': total_websites,
        'website_count': total_websites,  # Alias
        'total_policies': total_policies,
        'policy_count': total_policies,    # Alias
        'total_terms': total_terms,
        'terms_count': total_terms,        # Alias
        'total_changes': total_changes,
        'change_count': total_changes,      # Alias
        'total_documents': total_policies + total_terms,
        'major_changes': major_changes,
        'unread_notifications': unread_notifications,
        'freshness': freshness,
        'recent_updates': recent_updates
    }
