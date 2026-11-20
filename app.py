"""
app.py
Privacy Policy and Terms & Conditions Change Tracker
Backend: Python (Flask)
Database: SQLite
Frontend: HTML only (Zero JavaScript, Zero CSS Frameworks)
"""

import os
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

import database as db
import diff_utils

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'privacy_tracker_super_secret_key_2024')

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
def inject_current_user():
    """
    Injects logged-in user information into all HTML templates.
    """
    user = None
    if 'user_id' in session:
        user = db.get_user_by_id(session['user_id'])
    return {'current_user': user}


# ====================================================================
# HOME & AUTHENTICATION ROUTES
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
        flash("Registration successful! Welcome to Policy Tracker.", "success")
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


# ====================================================================
# DASHBOARD
# ====================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard:
    - Displays overall statistics (websites, policies, terms, changes)
    - Lists all tracked websites
    - Displays recently updated websites & change events
    """
    user_id = session['user_id']
    search_query = request.args.get('q', '').strip()

    stats = db.get_dashboard_stats(user_id)
    websites = db.get_websites_by_user(user_id, search_query if search_query else None)

    return render_template(
        'dashboard.html',
        stats=stats,
        websites=websites,
        search_query=search_query
    )


# ====================================================================
# WEBSITE MANAGEMENT (CRUD)
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

    return render_template(
        'website_details.html',
        website=website,
        current_policy=current_policy,
        current_terms=current_terms,
        policy_history=policy_history,
        terms_history=terms_history,
        change_history=change_history
    )


@app.route('/websites/<int:website_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_website(website_id):
    """
    Update Website details (name and URL).
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        website_name = request.form.get('website_name', '').strip()
        website_url = request.form.get('website_url', '').strip()

        if not website_name or not website_url:
            flash("Website Name and URL are both required.", "error")
            return render_template('edit_website.html', website=website)

        if not (website_url.startswith('http://') or website_url.startswith('https://')):
            website_url = 'https://' + website_url

        db.update_website(website_id, user_id, website_name, website_url)
        flash("Website details updated successfully.", "success")
        return redirect(url_for('website_details', website_id=website_id))

    return render_template('edit_website.html', website=website)


@app.route('/websites/<int:website_id>/delete', methods=['POST'])
@login_required
def delete_website(website_id):
    """
    Delete Website:
    Cascades and deletes associated policies, terms, and history records.
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    db.delete_website(website_id, user_id)
    flash(f"Website '{website['website_name']}' and all its history were deleted.", "info")
    return redirect(url_for('dashboard'))


# ====================================================================
# PRIVACY POLICY TRACKING & HISTORY
# ====================================================================

@app.route('/websites/<int:website_id>/privacy-history')
@login_required
def privacy_history(website_id):
    """
    Privacy Policy History Page:
    Lists all saved versions of the Privacy Policy for the selected website.
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
    Stores the new version content, increments version number,
    and logs change in ChangeHistory.
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
        flash(f"Privacy Policy Version {new_version} saved successfully!", "success")
        return redirect(url_for('privacy_history', website_id=website_id))

    return render_template('update_policy.html', website=website, latest=latest)


# ====================================================================
# TERMS & CONDITIONS TRACKING & HISTORY
# ====================================================================

@app.route('/websites/<int:website_id>/terms-history')
@login_required
def terms_history(website_id):
    """
    Terms & Conditions History Page:
    Lists all stored versions of the Terms & Conditions for the selected website.
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
    Stores the new version content, increments version number,
    and logs change in ChangeHistory.
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
        flash(f"Terms & Conditions Version {new_version} saved successfully!", "success")
        return redirect(url_for('terms_history', website_id=website_id))

    return render_template('update_terms.html', website=website, latest=latest)


# ====================================================================
# COMPARE VERSIONS (IDENTIFY & DISPLAY CHANGES)
# ====================================================================

@app.route('/websites/<int:website_id>/compare')
@login_required
def compare_versions(website_id):
    """
    Compares two versions of either Privacy Policy or Terms & Conditions.
    Uses pure Python difflib to generate:
    - Change summary statistics (lines added, deleted, unchanged)
    - Side-by-side comparison table
    - Unified line-by-line colored diff
    Requires zero client-side JavaScript!
    """
    user_id = session['user_id']
    website = db.get_website_by_id(website_id, user_id)
    if not website:
        flash("Website not found or access denied.", "error")
        return redirect(url_for('dashboard'))

    doc_type = request.args.get('type', 'policy')  # 'policy' or 'terms'
    v1 = request.args.get('v1', type=int)
    v2 = request.args.get('v2', type=int)
    view_mode = request.args.get('mode', 'side_by_side')  # 'side_by_side' or 'inline'

    if doc_type == 'terms':
        all_versions = db.get_terms_history(website_id)
        doc_title = "Terms & Conditions"
    else:
        doc_type = 'policy'
        all_versions = db.get_privacy_policy_history(website_id)
        doc_title = "Privacy Policy"

    version_numbers = [item['version'] for item in all_versions]

    # Default version selection if missing
    if not v1 or not v2:
        if len(version_numbers) >= 2:
            v2 = version_numbers[0]  # latest
            v1 = version_numbers[1]  # previous
        elif len(version_numbers) == 1:
            v1 = version_numbers[0]
            v2 = version_numbers[0]

    # Fetch contents
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

    # Compute diff and stats in Python
    stats = diff_utils.get_diff_statistics(content1, content2)
    side_by_side_rows = diff_utils.generate_side_by_side_diff(content1, content2)
    inline_diff_html = diff_utils.generate_inline_diff(content1, content2)

    return render_template(
        'compare_versions.html',
        website=website,
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
        view_mode=view_mode
    )


# ====================================================================
# GLOBAL CHANGE HISTORY
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
    # Initialize DB if not already existing
    if not os.path.exists(db.DATABASE_FILE):
        db.init_db()
    app.run(debug=True, host='127.0.0.1', port=5000)
