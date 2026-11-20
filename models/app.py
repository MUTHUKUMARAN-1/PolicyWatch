"""
app.py
PolicyWatch - Unified Web Application
Full Integration:
- Module 1: Web Scraping & Data Collection (ptct-scraper)
- Module 2: Relational DBMS Core (SQLite tracker.db)
- Module 3: User Authentication & Session Management
- Module 4: Search, Multi-Criteria Filtering, and Diff View
- Module 5: Notifications & Freshness Tracking
"""

import os
import json
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

from . import database as db
from . import diff_utils
from . import scraper_service

app = Flask(__name__, template_folder='../templates')
app.secret_key = os.environ.get('SECRET_KEY', 'policywatch_unified_secret_key_2026')

# Ensure database is closed after each request
app.teardown_appcontext(db.close_db)


# ====================================================================
# AUTHENTICATION DECORATOR & CONTEXT PROCESSOR
# ====================================================================

def login_required(view_func):
    """
    Ensures user is logged in before accessing protected routes.
    """
    @wraps(view_func)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login', next=request.url))
        return view_func(**kwargs)
    return wrapped_view


@app.context_processor
def inject_global_data():
    """
    Injects logged-in user, unread notification count, and freshness summary into all templates.
    """
    user = None
    unread_count = 0
    freshness_summary = {'total': 0, 'fresh': 0, 'aging': 0, 'stale': 0, 'never_checked': 0}

    if 'user_id' in session:
        user = db.get_user_by_id(session['user_id'])
        if user:
            unread_count = db.get_unread_notifications_count(user['user_id'])
            freshness_summary = db.get_freshness_summary(user['user_id'])

    return {
        'current_user': user,
        'unread_notifications_count': unread_count,
        'freshness_summary': freshness_summary,
        'active_path': request.path
    }


# ====================================================================
# HOME & AUTHENTICATION ROUTES (Module 3)
# ====================================================================

@app.route('/')
def index():
    """
    Home page. If logged in, redirects to Dashboard.
    Otherwise shows public landing page.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User Registration: Validates inputs, hashes password, and creates account.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Data Validation
        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        if not email or '@' not in email or '.' not in email:
            errors.append("Please enter a valid email address.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Check uniqueness
        if not errors:
            if db.get_user_by_username(username):
                errors.append("Username is already taken. Please choose another.")
            elif db.get_user_by_email(email):
                errors.append("An account with this email already exists.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template('register.html', username=username, email=email)

        # Hash password and save to database
        password_hash = generate_password_hash(password)
        user_id = db.create_user(username, email, password_hash)

        # Automatically log user in
        session.clear()
        session['user_id'] = user_id
        session['username'] = username
        flash("Registration successful! Welcome to PolicyWatch.", "success")
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User Login: Authenticates username and password.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        if not identifier or not password:
            flash("Please enter both username/email and password.", "error")
            return render_template('login.html', identifier=identifier)

        # Search by username or email
        user = db.get_user_by_username(identifier)
        if not user:
            user = db.get_user_by_email(identifier)

        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}!", "success")

            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username/email or password.", "error")
            return render_template('login.html', identifier=identifier)

    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    Logs out the user and clears session data.
    """
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('login'))


@app.route('/profile')
@login_required
def profile():
    """
    User Profile View (Module 3).
    """
    user_id = session['user_id']
    user = db.get_user_by_id(user_id)
    stats = db.get_dashboard_stats(user_id)
    websites = db.get_websites_by_user(user_id)
    return render_template('profile.html', user=user, stats=stats, websites=websites)


# ====================================================================
# DASHBOARD (Module 6)
# ====================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """
    System Dashboard:
    - Real-time compliance monitoring metrics
    - Source freshness indicators
    - Tracked websites list with quick actions
    - Recent changes and unread notifications
    """
    user_id = session['user_id']
    search_query = request.args.get('q', '').strip()

    stats = db.get_dashboard_stats(user_id)
    websites = db.get_websites_by_user(user_id, search_query if search_query else None)
    recent_notifications = db.get_notifications_for_user(user_id, limit=5)
    freshness_list = db.get_all_source_freshness(user_id)

    return render_template(
        'dashboard.html',
        stats=stats,
        websites=websites,
        search_query=search_query,
        recent_notifications=recent_notifications,
        freshness_list=freshness_list
    )


# ====================================================================
# WEBSITE MANAGEMENT (CRUD - Module 2)
# ====================================================================

@app.route('/websites/add', methods=['GET', 'POST'])
@login_required
def add_website():
    """
    Create Website:
    Adds a new website with optional initial Privacy Policy and Terms & Conditions.
    """
    if request.method == 'POST':
        website_name = request.form.get('website_name', '').strip()
        website_url = request.form.get('website_url', '').strip()
        initial_policy = request.form.get('initial_policy', '').strip()
        initial_terms = request.form.get('initial_terms', '').strip()

        # Validation
        if not website_name:
            flash("Website Name is required.", "error")
            return render_template('add_website.html', website_name=website_name, website_url=website_url)

        if not website_url:
            flash("Website URL is required.", "error")
            return render_template('add_website.html', website_name=website_name, website_url=website_url)

        # Ensure scheme
        if not (website_url.startswith('http://') or website_url.startswith('https://')):
            website_url = 'https://' + website_url

        user_id = session['user_id']
        website_id = db.create_website(user_id, website_name, website_url)

        # Store initial policy if provided
        if initial_policy:
            db.add_privacy_policy(website_id, initial_policy)

        # Store initial terms if provided
        if initial_terms:
            db.add_terms_conditions(website_id, initial_terms)

        flash(f"Website '{website_name}' added successfully!", "success")
        return redirect(url_for('website_details', website_id=website_id))

    return render_template('add_website.html')


@app.route('/websites/<int:website_id>')
@login_required
def website_details(website_id):
    """
    Website Details Page:
    Shows website info, current active Privacy Policy and Terms & Conditions,
    and a summary of recent changes for this website.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    current_policy = db.get_latest_privacy_policy(website_id)
    current_terms = db.get_latest_terms_conditions(website_id)
    policy_history = db.get_privacy_policy_history(website_id)
    terms_history = db.get_terms_history(website_id)
    change_history = db.get_change_history_for_website(website_id)
    snapshots = db.get_recent_snapshots(website_id=website_id, limit=5)

    return render_template(
        'website_details.html',
        website=website,
        current_policy=current_policy,
        current_terms=current_terms,
        policy_history=policy_history,
        terms_history=terms_history,
        change_history=change_history,
        snapshots=snapshots
    )


@app.route('/websites/<int:website_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_website(website_id):
    """
    Edit Website:
    Updates website name and URL.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        website_name = request.form.get('website_name', '').strip()
        website_url = request.form.get('website_url', '').strip()

        if not website_name:
            flash("Website Name cannot be empty.", "error")
            return render_template('edit_website.html', website=website)

        if not website_url:
            flash("Website URL cannot be empty.", "error")
            return render_template('edit_website.html', website=website)

        if not (website_url.startswith('http://') or website_url.startswith('https://')):
            website_url = 'https://' + website_url

        db.update_website(website_id, user_id, website_name, website_url)
        flash(f"Website '{website_name}' updated successfully!", "success")
        return redirect(url_for('website_details', website_id=website_id))

    return render_template('edit_website.html', website=website)


@app.route('/websites/<int:website_id>/delete', methods=['POST'])
@login_required
def delete_website(website_id):
    """
    Delete Website:
    Removes website and cascades deletions to all associated policies,
    terms, and change logs.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    name = website['website_name']
    db.delete_website(website_id, user_id)
    flash(f"Website '{name}' and all associated versions were deleted.", "success")
    return redirect(url_for('dashboard'))


# ====================================================================
# PRIVACY POLICY & TERMS TRACKING (CRUD & HISTORY)
# ====================================================================

@app.route('/websites/<int:website_id>/privacy-history')
@login_required
def privacy_history(website_id):
    """
    Privacy Policy History Page.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    versions = db.get_privacy_policy_history(website_id)
    latest = db.get_latest_privacy_policy(website_id)

    return render_template(
        'privacy_history.html',
        website=website,
        versions=versions,
        latest=latest
    )


@app.route('/websites/<int:website_id>/privacy/update', methods=['GET', 'POST'])
@login_required
def update_privacy_policy(website_id):
    """
    Save Updated Privacy Policy:
    Stores new version, increments version number, triggers change detection,
    and creates audit record and notification.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    latest = db.get_latest_privacy_policy(website_id)

    if request.method == 'POST':
        new_content = request.form.get('policy_content', '').strip()
        if not new_content:
            flash("Privacy Policy content cannot be empty.", "error")
            return render_template('update_policy.html', website=website, latest=latest)

        if latest and new_content == latest['policy_content'].strip():
            flash("No changes detected compared to the current version.", "info")
            return render_template('update_policy.html', website=website, latest=latest)

        _, new_version = db.add_privacy_policy(website_id, new_content)
        flash(f"Privacy Policy Version {new_version} saved successfully! Change classified.", "success")
        return redirect(url_for('privacy_history', website_id=website_id))

    return render_template('update_policy.html', website=website, latest=latest)


@app.route('/websites/<int:website_id>/terms-history')
@login_required
def terms_history(website_id):
    """
    Terms & Conditions History Page.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    versions = db.get_terms_history(website_id)
    latest = db.get_latest_terms_conditions(website_id)

    return render_template(
        'terms_history.html',
        website=website,
        versions=versions,
        latest=latest
    )


@app.route('/websites/<int:website_id>/terms/update', methods=['GET', 'POST'])
@login_required
def update_terms_conditions(website_id):
    """
    Save Updated Terms & Conditions:
    Stores new version, increments version number, triggers change detection,
    and creates audit record and notification.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    latest = db.get_latest_terms_conditions(website_id)

    if request.method == 'POST':
        new_content = request.form.get('terms_content', '').strip()
        if not new_content:
            flash("Terms & Conditions content cannot be empty.", "error")
            return render_template('update_terms.html', website=website, latest=latest)

        if latest and new_content == latest['terms_content'].strip():
            flash("No changes detected compared to the current version.", "info")
            return render_template('update_terms.html', website=website, latest=latest)

        _, new_version = db.add_terms_conditions(website_id, new_content)
        flash(f"Terms & Conditions Version {new_version} saved successfully! Change classified.", "success")
        return redirect(url_for('terms_history', website_id=website_id))

    return render_template('update_terms.html', website=website, latest=latest)


# ====================================================================
# MODULE 4: SEARCH, MULTI-CRITERIA FILTERING, AND DIFF VIEW
# ====================================================================

@app.route('/search')
@login_required
def search():
    """
    Module 4A & 4B: Unified Search & Multi-Criteria Filtering:
    Searches websites, documents, change summaries, categories, and full text.
    Filters: website, doc_type, severity, category, change_type, review_status, date range.
    """
    user_id = session['user_id']
    query_str = request.args.get('q', '').strip()
    site_id = request.args.get('site_id', type=int)
    doc_type = request.args.get('doc_type', 'all')
    severity = request.args.get('severity', 'all')
    category = request.args.get('category', 'all')
    change_type = request.args.get('change_type', 'all')
    review_status = request.args.get('review_status', 'all')
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    search_res = db.search_records(
        user_id=user_id,
        query_str=query_str,
        site_id=site_id,
        doc_type=doc_type,
        severity=severity,
        category=category,
        change_type=change_type,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to
    )

    user_websites = db.get_websites_by_user(user_id)
    categories = db.get_distinct_categories()
    severities = db.get_distinct_severities()

    return render_template(
        'search.html',
        query_str=query_str,
        site_id=site_id,
        doc_type=doc_type,
        severity=severity,
        category=category,
        change_type=change_type,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
        results=search_res['changes'],
        matching_sites=search_res['matching_sites'],
        total_results=search_res['count'],
        websites=user_websites,
        categories=categories,
        severities=severities
    )


@app.route('/compare')
@app.route('/websites/<int:website_id>/compare')
@login_required
def compare_versions(website_id=None):
    """
    Module 4C & 4D: Professional Diff View & Historical Version Selection.
    Supports:
    - Side-by-side comparison
    - Line-by-line unified diff
    - NLP clause classification, severity rating, and legal rationale (change_detection)
    - Validates version selection to prevent invalid comparisons
    """
    user_id = session['user_id']
    websites = db.get_websites_by_user(user_id)

    if not websites:
        flash("No websites tracked yet. Please add a website first.", "info")
        return redirect(url_for('add_website'))

    # If no website_id given, default to first website
    if not website_id:
        target_id = request.args.get('website_id', type=int)
        if target_id:
            website_id = target_id
        else:
            website_id = websites[0]['website_id']

    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    doc_type = request.args.get('type', 'policy')
    v1 = request.args.get('v1', type=int)
    v2 = request.args.get('v2', type=int)
    view_mode = request.args.get('mode', 'side_by_side')
    include_formatting = request.args.get('formatting', 'true').lower() == 'true'

    if doc_type == 'terms':
        all_versions = db.get_terms_history(website_id)
        doc_title = "Terms & Conditions"
    else:
        doc_type = 'policy'
        all_versions = db.get_privacy_policy_history(website_id)
        doc_title = "Privacy Policy"

    version_numbers = [item['version'] for item in all_versions]

    # Handle default version selection
    if not v1 or not v2:
        if len(version_numbers) >= 2:
            v2 = version_numbers[0]  # latest
            v1 = version_numbers[1]  # previous
        elif len(version_numbers) == 1:
            v1 = version_numbers[0]
            v2 = version_numbers[0]

    # Validation: same version comparison warning
    same_version_warning = False
    if v1 and v2 and v1 == v2 and len(version_numbers) > 1:
        same_version_warning = True

    # Fetch document contents
    doc1 = None
    doc2 = None
    if doc_type == 'policy':
        if v1:
            doc1 = db.get_privacy_policy_by_version(website_id, v1)
        if v2:
            doc2 = db.get_privacy_policy_by_version(website_id, v2)
    else:
        if v1:
            doc1 = db.get_terms_by_version(website_id, v1)
        if v2:
            doc2 = db.get_terms_by_version(website_id, v2)

    content1 = doc1['policy_content'] if (doc1 and doc_type == 'policy') else (doc1['terms_content'] if doc1 else '')
    content2 = doc2['policy_content'] if (doc2 and doc_type == 'policy') else (doc2['terms_content'] if doc2 else '')

    # Compute difflib statistics and rows
    stats = diff_utils.get_diff_statistics(content1, content2)
    side_by_side_rows = diff_utils.generate_side_by_side_diff(content1, content2)
    inline_diff_html = diff_utils.generate_inline_diff(content1, content2)

    # Invoke change_detection semantic NLP classifier
    classification_report = None
    try:
        from change_detection.api import detect_changes
        report = detect_changes(content1, content2, document_id=f"{website['website_name']}_{doc_type}", include_formatting=include_formatting)
        classification_report = report.to_dict()
    except Exception:
        pass

    return render_template(
        'compare_versions.html',
        website=website,
        websites=websites,
        doc_type=doc_type,
        doc_title=doc_title,
        all_versions=all_versions,
        v1=v1,
        v2=v2,
        doc1=doc1,
        doc2=doc2,
        stats=stats,
        side_by_side_rows=side_by_side_rows,
        inline_diff_html=inline_diff_html,
        view_mode=view_mode,
        include_formatting=include_formatting,
        same_version_warning=same_version_warning,
        classification_report=classification_report
    )


@app.route('/changes')
@login_required
def changes_list():
    """
    Module 4: Detected Changes Exploration Feed.
    Allows filtering all detected changes by website, severity, category, and review status.
    """
    user_id = session['user_id']
    site_id = request.args.get('site_id', type=int)
    severity = request.args.get('severity', 'all')
    category = request.args.get('category', 'all')
    review_status = request.args.get('review_status', 'all')

    search_res = db.search_records(
        user_id=user_id,
        site_id=site_id,
        severity=severity,
        category=category,
        review_status=review_status
    )

    user_websites = db.get_websites_by_user(user_id)
    categories = db.get_distinct_categories()
    severities = db.get_distinct_severities()

    return render_template(
        'changes.html',
        changes=search_res['changes'],
        websites=user_websites,
        selected_site=site_id,
        selected_severity=severity,
        selected_category=category,
        selected_review=review_status,
        categories=categories,
        severities=severities
    )


@app.route('/changes/<int:change_id>')
@login_required
def change_detail(change_id):
    """
    Module 4E: Change Detail View:
    Displays change description, previous and new content, category, severity,
    rationale, timestamps, and review status workflow.
    """
    user_id = session['user_id']
    change = db.get_change_by_id(change_id, user_id)
    if not change:
        flash("Change record not found or access denied.", "error")
        return redirect(url_for('changes_list'))

    # Fetch older and newer version contents
    w_id = change['website_id']
    c_type = change['change_type']
    old_v = change['old_version']
    new_v = change['new_version']

    old_doc = None
    new_doc = None
    if c_type == 'Privacy Policy':
        if old_v:
            old_doc = db.get_privacy_policy_by_version(w_id, old_v)
        if new_v:
            new_doc = db.get_privacy_policy_by_version(w_id, new_v)
    else:
        if old_v:
            old_doc = db.get_terms_by_version(w_id, old_v)
        if new_v:
            new_doc = db.get_terms_by_version(w_id, new_v)

    old_text = old_doc['policy_content'] if (old_doc and c_type == 'Privacy Policy') else (old_doc['terms_content'] if old_doc else '')
    new_text = new_doc['policy_content'] if (new_doc and c_type == 'Privacy Policy') else (new_doc['terms_content'] if new_doc else '')

    diff_html = diff_utils.generate_inline_diff(old_text, new_text)

    return render_template(
        'change_detail.html',
        change=change,
        old_doc=old_doc,
        new_doc=new_doc,
        old_text=old_text,
        new_text=new_text,
        diff_html=diff_html
    )


@app.route('/changes/<int:change_id>/review', methods=['POST'])
@login_required
def update_change_review(change_id):
    """
    Updates the review status for a detected change (confirmed / rejected).
    """
    user_id = session['user_id']
    change = db.get_change_by_id(change_id, user_id)
    if not change:
        flash("Change record not found or access denied.", "error")
        return redirect(url_for('changes_list'))

    new_status = request.form.get('review_status', 'unreviewed')
    review_notes = request.form.get('review_notes', '').strip()
    reviewer_name = session.get('username', 'Admin')

    db.update_change_review_status(change_id, new_status, reviewed_by=reviewer_name, review_notes=review_notes)
    flash(f"Change #{change_id} marked as '{new_status}' by {reviewer_name}.", "success")
    return redirect(url_for('change_detail', change_id=change_id))


# ====================================================================
# MODULE 5: NOTIFICATIONS & FRESHNESS TRACKING
# ====================================================================

@app.route('/notifications')
@login_required
def notifications_hub():
    """
    Module 5: Notification Center.
    Lists notifications with read/unread filtering and mark-as-read actions.
    """
    user_id = session['user_id']
    unread_only = request.args.get('filter') == 'unread'
    notifications = db.get_notifications_for_user(user_id, unread_only=unread_only, limit=100)
    return render_template('notifications.html', notifications=notifications, unread_only=unread_only)


@app.route('/notifications/<int:notification_id>/read', methods=['GET', 'POST'])
@login_required
def mark_notification_read(notification_id):
    """
    Marks a single notification as read.
    """
    db.mark_notification_as_read(notification_id)
    flash("Notification marked as read.", "success")
    return redirect(request.referrer or url_for('notifications_hub'))


@app.route('/notifications/read-all', methods=['GET', 'POST'])
@login_required
def mark_all_notifications_read():
    """
    Marks all notifications for the user as read.
    """
    user_id = session['user_id']
    count = db.mark_all_notifications_as_read(user_id)
    flash(f"{count} notifications marked as read.", "success")
    return redirect(url_for('notifications_hub'))


@app.route('/freshness')
@login_required
def freshness_monitor():
    """
    Module 5: Source Freshness Tracking Dashboard.
    Displays last successful check, last changed timestamp, and 24h / 72h status.
    """
    user_id = session['user_id']
    freshness_list = db.get_all_source_freshness(user_id)
    summary = db.get_freshness_summary(user_id)
    return render_template('freshness.html', freshness_list=freshness_list, summary=summary)


# ====================================================================
# MODULE 1: WEB SCRAPER & DATA COLLECTION
# ====================================================================

@app.route('/scraper')
@login_required
def scraper_hub():
    """
    Module 1: Web Scraping and Data Collection Dashboard:
    - Lists sources, approval status, and freshness
    - Displays snapshot archives and content hashes
    - Safe manual offline collection trigger
    """
    user_id = session['user_id']
    sources = scraper_service.get_scraper_sources(user_id)
    snapshots = db.get_recent_snapshots(limit=30)
    return render_template('scraper.html', sources=sources, snapshots=snapshots)


@app.route('/scraper/refresh/<int:website_id>', methods=['GET', 'POST'])
@login_required
def scraper_refresh_website(website_id):
    """
    Triggers a manual offline collection cycle for a tracked website.
    """
    user_id = session['user_id']
    result = scraper_service.run_offline_refresh(website_id, user_id)
    if result.get('success'):
        flash(result['message'], "success" if result.get('is_changed') else "info")
    else:
        flash(result.get('error', "Refresh failed."), "error")
    return redirect(request.referrer or url_for('scraper_hub'))


@app.route('/scraper/demo-cycle', methods=['POST'])
@login_required
def scraper_run_demo():
    """
    Executes the 7-cycle ptct.demo scripted refresh scenario.
    """
    result = scraper_service.run_full_offline_demo()
    if result.get('success'):
        flash(result['message'], "success")
    else:
        flash(result.get('error', "Demo run failed."), "error")
    return redirect(url_for('scraper_hub'))


# ====================================================================
# GLOBAL AUDIT LOG
# ====================================================================

@app.route('/history')
@login_required
def all_history():
    """
    Displays complete change audit log for all websites tracked by the user.
    """
    user_id = session['user_id']
    history_records = db.get_all_change_history(user_id, limit=100)
    return render_template('history.html', history_records=history_records)


# ====================================================================
# ERROR HANDLERS
# ====================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('base.html', not_found=True), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('base.html', server_error=True), 500


# ====================================================================
# RUN SERVER
# ====================================================================

if __name__ == '__main__':
    if not os.path.exists(db.DATABASE_FILE):
        db.init_db()
    app.run(debug=True, host='127.0.0.1', port=5000)
