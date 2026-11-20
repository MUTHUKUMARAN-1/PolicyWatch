import sqlite3
import os
from flask import g, has_app_context

DATABASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tracker.db')
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')


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
        return g.db
    else:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn


def close_db(e=None):
    """
    Closes the database connection at the end of the request.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


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
# USER CRUD OPERATIONS
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
# WEBSITE CRUD OPERATIONS
# ====================================================================

def create_website(user_id, website_name, website_url):
    """
    Adds a new website tracked by the user.
    """
    query = """
        INSERT INTO Websites (user_id, website_name, website_url)
        VALUES (?, ?, ?);
    """
    return execute_db(query, (user_id, website_name.strip(), website_url.strip()))


def get_websites_by_user(user_id, search_query=None):
    """
    Lists all websites belonging to a user, with optional search filter.
    Includes latest policy version and terms version using subqueries.
    """
    if search_query:
        query = """
            SELECT w.*,
                   (SELECT MAX(version) FROM PrivacyPolicies WHERE website_id = w.website_id) AS current_policy_version,
                   (SELECT MAX(updated_at) FROM PrivacyPolicies WHERE website_id = w.website_id) AS last_policy_update,
                   (SELECT MAX(version) FROM TermsConditions WHERE website_id = w.website_id) AS current_terms_version,
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
                   (SELECT MAX(version) FROM PrivacyPolicies WHERE website_id = w.website_id) AS current_policy_version,
                   (SELECT MAX(updated_at) FROM PrivacyPolicies WHERE website_id = w.website_id) AS last_policy_update,
                   (SELECT MAX(version) FROM TermsConditions WHERE website_id = w.website_id) AS current_terms_version,
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
    policies, terms, and change history records are automatically deleted.
    """
    query = "DELETE FROM Websites WHERE website_id = ? AND user_id = ?;"
    execute_db(query, (website_id, user_id))


# ====================================================================
# PRIVACY POLICY TRACKING (CRUD & VERSIONING)
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
    Automatically increments version number and records in ChangeHistory.
    """
    latest = get_latest_privacy_policy(website_id)
    if latest:
        old_version = latest['version']
        new_version = old_version + 1
    else:
        old_version = None
        new_version = 1

    query = """
        INSERT INTO PrivacyPolicies (website_id, policy_content, version)
        VALUES (?, ?, ?);
    """
    policy_id = execute_db(query, (website_id, policy_content.strip(), new_version))

    # Record in ChangeHistory table
    record_change(
        website_id=website_id,
        change_type='Privacy Policy',
        old_version=old_version,
        new_version=new_version
    )

    return policy_id, new_version


def delete_privacy_policy_version(policy_id, website_id):
    """
    Deletes a single privacy policy version.
    """
    query = "DELETE FROM PrivacyPolicies WHERE policy_id = ? AND website_id = ?;"
    execute_db(query, (policy_id, website_id))


# ====================================================================
# TERMS & CONDITIONS TRACKING (CRUD & VERSIONING)
# ====================================================================

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
    Automatically increments version number and records in ChangeHistory.
    """
    latest = get_latest_terms_conditions(website_id)
    if latest:
        old_version = latest['version']
        new_version = old_version + 1
    else:
        old_version = None
        new_version = 1

    query = """
        INSERT INTO TermsConditions (website_id, terms_content, version)
        VALUES (?, ?, ?);
    """
    terms_id = execute_db(query, (website_id, terms_content.strip(), new_version))

    # Record in ChangeHistory table
    record_change(
        website_id=website_id,
        change_type='Terms & Conditions',
        old_version=old_version,
        new_version=new_version
    )

    return terms_id, new_version


def delete_terms_version(terms_id, website_id):
    """
    Deletes a single terms version.
    """
    query = "DELETE FROM TermsConditions WHERE terms_id = ? AND website_id = ?;"
    execute_db(query, (terms_id, website_id))


# ====================================================================
# CHANGE HISTORY MANAGEMENT
# ====================================================================

def record_change(website_id, change_type, old_version, new_version):
    """
    Inserts an audit record into ChangeHistory.
    """
    query = """
        INSERT INTO ChangeHistory (website_id, change_type, old_version, new_version)
        VALUES (?, ?, ?, ?);
    """
    return execute_db(query, (website_id, change_type, old_version, new_version))


def get_change_history_for_website(website_id):
    """
    Returns the complete change history for a specific website.
    """
    query = """
        SELECT ch.*, w.website_name
        FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE ch.website_id = ?
        ORDER BY ch.change_date DESC;
    """
    return query_db(query, (website_id,))


def get_all_change_history(user_id, limit=50):
    """
    Returns full change history across all websites owned by the user.
    """
    query = """
        SELECT ch.*, w.website_name, w.website_url
        FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE w.user_id = ?
        ORDER BY ch.change_date DESC
        LIMIT ?;
    """
    return query_db(query, (user_id, limit))


# ====================================================================
# DASHBOARD METRICS & RECENT ACTIVITY
# ====================================================================

def get_dashboard_stats(user_id):
    """
    Aggregates dashboard metrics for the logged-in user:
    - Total websites tracked
    - Total policy updates
    - Total terms updates
    - Total recorded changes
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

    # 5. Recently updated websites (Top 5 based on ChangeHistory)
    recent_updates = db.execute("""
        SELECT ch.change_id, ch.change_type, ch.old_version, ch.new_version, ch.change_date,
               w.website_id, w.website_name, w.website_url
        FROM ChangeHistory ch
        JOIN Websites w ON ch.website_id = w.website_id
        WHERE w.user_id = ?
        ORDER BY ch.change_date DESC
        LIMIT 6;
    """, (user_id,)).fetchall()

    return {
        'total_websites': total_websites,
        'total_policies': total_policies,
        'total_terms': total_terms,
        'total_changes': total_changes,
        'recent_updates': recent_updates
    }
