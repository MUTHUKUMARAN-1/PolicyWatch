"""
sample_data.py
PolicyWatch - Populates tracker.db with realistic, verified sample data.
Includes sample users, websites, multi-version privacy policies, terms & conditions,
classified change history logs, notifications, and source freshness records.
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash
from .database import init_db, DATABASE_FILE


def seed_sample_data():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Clear existing tables in reverse order of foreign key dependency
    cursor.execute("DROP TABLE IF EXISTS m5_notifications;")
    cursor.execute("DROP TABLE IF EXISTS m5_source_freshness;")
    cursor.execute("DROP TABLE IF EXISTS ScraperSnapshots;")
    cursor.execute("DROP TABLE IF EXISTS ChangeHistory;")
    cursor.execute("DROP TABLE IF EXISTS PrivacyPolicies;")
    cursor.execute("DROP TABLE IF EXISTS TermsConditions;")
    cursor.execute("DROP TABLE IF EXISTS Websites;")
    cursor.execute("DROP TABLE IF EXISTS Users;")
    conn.commit()
    conn.close()

    # Recreate clean schema
    init_db()

    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    print("[*] Seeding sample users...")
    users = [
        ('admin', 'admin@tracker.local', generate_password_hash('admin123')),
        ('john_doe', 'john@example.com', generate_password_hash('password123'))
    ]
    cursor.executemany(
        "INSERT INTO Users (username, email, password) VALUES (?, ?, ?);",
        users
    )
    admin_id = 1
    john_id = 2

    print("[*] Seeding sample websites...")
    websites = [
        (admin_id, 'Acme Cloud Services', 'https://acmecloud.io'),
        (admin_id, 'SocialPulse Media', 'https://socialpulse.com'),
        (admin_id, 'PaySwift Gateway', 'https://payswift.net'),
        (john_id, 'DevPortal Community', 'https://devportal.org')
    ]
    cursor.executemany(
        "INSERT INTO Websites (user_id, website_name, website_url) VALUES (?, ?, ?);",
        websites
    )
    acme_id = 1
    social_id = 2
    payswift_id = 3
    devportal_id = 4

    print("[*] Seeding Privacy Policies (multiple versions)...")

    # Acme Cloud Privacy Policies
    acme_pp_v1 = """Acme Cloud Privacy Policy (Version 1.0)
Effective Date: January 15, 2024

1. Information We Collect
We collect standard personal information including:
- Your full name and business email address
- Company name and billing address
- Login credentials (username and hashed passwords)
- Basic web server access logs and browser cookie identifiers

2. How We Use Information
We use your collected information strictly to:
- Provide cloud infrastructure services
- Process recurring subscription payments
- Send vital service announcements and maintenance notices

3. Data Sharing
We do not sell your personal data to third parties. We only share data with essential infrastructure service providers necessary to operate the cloud platform."""

    acme_pp_v2 = """Acme Cloud Privacy Policy (Version 2.0 - GDPR/CCPA Update)
Effective Date: June 1, 2024

1. Information We Collect
We collect personal information including:
- Your full name and business email address
- Company name and billing address
- Login credentials (username and hashed passwords)
- Device telemetry, IP addresses, and session diagnostic cookies
- Location data derived from IP addresses for security compliance

2. How We Use Information
We use your collected information strictly to:
- Provide and optimize cloud infrastructure services
- Process recurring subscription payments securely
- Send vital service announcements, security alerts, and maintenance notices
- Comply with international data regulations (GDPR and CCPA)

3. Data Sharing and International Transfers
We do not sell personal data to advertisers. We share information only with:
- Accredited payment gateways (Stripe/PayPal)
- Sub-processors bound by Standard Contractual Clauses (SCCs)
- Legal authorities when mandated by valid court subpoena

4. User Rights and Data Deletion
Under GDPR and CCPA, users have the right to access, rectify, export, and request total erasure of their personal information at any time via account settings."""

    acme_pp_v3 = """Acme Cloud Privacy Policy (Version 3.0 - AI Transparency Update)
Effective Date: October 10, 2024

1. Information We Collect
We collect personal information including:
- Your full name and business email address
- Company name and billing address
- Login credentials (username and hashed passwords)
- Device telemetry, IP addresses, and session diagnostic cookies
- Location data derived from IP addresses for security compliance

2. How We Use Information
We use your collected information strictly to:
- Provide and optimize cloud infrastructure services
- Process recurring subscription payments securely
- Send vital service announcements, security alerts, and maintenance notices
- Comply with international data regulations (GDPR and CCPA)
- Train optional AI assistive tools ONLY when explicitly opted-in by the account administrator

3. Data Sharing and International Transfers
We do not sell personal data to advertisers. We share information only with:
- Accredited payment gateways (Stripe/PayPal)
- Sub-processors bound by Standard Contractual Clauses (SCCs)
- Legal authorities when mandated by valid court subpoena

4. User Rights and Data Deletion
Under GDPR and CCPA, users have the right to access, rectify, export, and request total erasure of their personal information at any time via account settings.

5. Generative AI and Customer Data Safeguard
Customer proprietary files, database records, and proprietary cloud storage are NEVER used to train shared machine learning models without express written authorization."""

    cursor.execute("INSERT INTO PrivacyPolicies (website_id, policy_content, version, updated_at) VALUES (?, ?, ?, '2024-01-15 10:00:00');", (acme_id, acme_pp_v1, 1))
    cursor.execute("INSERT INTO PrivacyPolicies (website_id, policy_content, version, updated_at) VALUES (?, ?, ?, '2024-06-01 14:30:00');", (acme_id, acme_pp_v2, 2))
    cursor.execute("INSERT INTO PrivacyPolicies (website_id, policy_content, version, updated_at) VALUES (?, ?, ?, '2024-10-10 09:15:00');", (acme_id, acme_pp_v3, 3))

    # SocialPulse Privacy Policy
    social_pp_v1 = """SocialPulse Privacy Policy (Version 1.0)
Effective Date: March 1, 2024

1. Personal Information Collected:
- Profile name, handle, email address, and avatar image.
- Posts, comments, likes, and social interactions.

2. Usage:
Used solely to display your social profile and connect you with peers."""

    social_pp_v2 = """SocialPulse Privacy Policy (Version 2.0 - Biometrics & Ad Bidding)
Effective Date: August 20, 2024

1. Personal Information Collected:
- Profile name, handle, email address, and avatar image.
- Posts, comments, likes, and social interactions.
- Device advertising identifiers (IDFA, AAID) and approximate geographic location.
- Facial geometry vectors extracted from video uploads for avatar generation.

2. Usage and Advertising:
- Used to power your social feed and social graph.
- Used to personalize sponsored content and relevant advertising banners.
- Real-time programmatic advertising bidding based on aggregated user engagement signals.
- Users can disable personalized ad tracking in the profile settings menu."""

    cursor.execute("INSERT INTO PrivacyPolicies (website_id, policy_content, version, updated_at) VALUES (?, ?, ?, '2024-03-01 11:00:00');", (social_id, social_pp_v1, 1))
    cursor.execute("INSERT INTO PrivacyPolicies (website_id, policy_content, version, updated_at) VALUES (?, ?, ?, '2024-08-20 16:45:00');", (social_id, social_pp_v2, 2))

    # PaySwift Privacy Policy
    payswift_pp_v1 = """PaySwift Privacy Policy (Version 1.0)
Effective Date: February 10, 2024

1. Financial and Personal Data
We collect merchant identity, business license, and verified bank account routing numbers.
All financial transactions are tokenized in compliance with PCI-DSS Level 1 standards."""
    cursor.execute("INSERT INTO PrivacyPolicies (website_id, policy_content, version, updated_at) VALUES (?, ?, ?, '2024-02-10 08:00:00');", (payswift_id, payswift_pp_v1, 1))

    # DevPortal Privacy Policy
    devportal_pp_v1 = """DevPortal Community Privacy Notice (Version 1.0)
Effective Date: April 1, 2024

1. Developer Information
We collect GitHub usernames, public repository contributions, and forum posts.
No tracking cookies are used on documentation pages."""
    cursor.execute("INSERT INTO PrivacyPolicies (website_id, policy_content, version, updated_at) VALUES (?, ?, ?, '2024-04-01 09:00:00');", (devportal_id, devportal_pp_v1, 1))

    print("[*] Seeding Terms & Conditions (multiple versions)...")

    # Acme Cloud Terms
    acme_tc_v1 = """Acme Cloud Terms of Service (Version 1.0)
Effective Date: January 15, 2024

1. Acceptance of Terms
By creating an account on Acme Cloud, you agree to abide by these Terms of Service.

2. Subscription & Payments
Subscriptions are billed monthly in advance. Cancellation requires 30 days written notice prior to the next billing cycle.

3. Acceptable Use
You must not use our servers for cryptomining, network denial-of-service attacks, or transmitting malicious code.

4. Limitation of Liability
Acme Cloud provides infrastructure on an 'as-is' basis without warranties of uninterrupted uptime."""

    acme_tc_v2 = """Acme Cloud Terms of Service (Version 2.0)
Effective Date: July 15, 2024

1. Acceptance of Terms
By creating an account on Acme Cloud, you agree to abide by these Terms of Service.

2. Subscription & Payments
Subscriptions are billed monthly in advance. Cancellation requires 14 days notice (updated from 30 days) prior to the next billing cycle.

3. Acceptable Use
You must not use our servers for cryptomining, network denial-of-service attacks, transmitting malicious code, or unsolicited bulk email (SPAM).

4. Limitation of Liability and SLA
Acme Cloud guarantees 99.9% monthly uptime. Total aggregate liability for any service failure is strictly capped at the fees paid by you in the preceding 3 months, or $500, whichever is lower."""

    cursor.execute("INSERT INTO TermsConditions (website_id, terms_content, version, updated_at) VALUES (?, ?, ?, '2024-01-15 10:00:00');", (acme_id, acme_tc_v1, 1))
    cursor.execute("INSERT INTO TermsConditions (website_id, terms_content, version, updated_at) VALUES (?, ?, ?, '2024-07-15 12:00:00');", (acme_id, acme_tc_v2, 2))

    # PaySwift Terms
    payswift_tc_v1 = """PaySwift Merchant Terms & Conditions (Version 1.0)
Effective Date: February 10, 2024

1. Processing Fees
Standard processing fee is 2.9% + 30 cents per completed transaction.

2. Payout Schedule
Merchant payouts are batched and disbursed on a rolling 7-day schedule."""

    payswift_tc_v2 = """PaySwift Merchant Terms & Conditions (Version 2.0)
Effective Date: September 5, 2024

1. Processing Fees
Standard processing fee is 2.9% + 30 cents per completed transaction.
High-volume merchants processing over $100,000 monthly qualify for custom tiered interchange rates.

2. Payout Schedule & Instant Transfer
Merchant payouts are batched and disbursed on a rolling 7-day schedule.
Eligible merchants may now utilize Instant Payout for an additional 1.0% fee.

3. Chargebacks and Dispute Defense
Merchants are assessed a $15 fee per disputed chargeback unless covered by PaySwift Dispute Shield protection.

4. Mandatory Arbitration
All merchant disputes must proceed individually under American Arbitration Association rules."""

    cursor.execute("INSERT INTO TermsConditions (website_id, terms_content, version, updated_at) VALUES (?, ?, ?, '2024-02-10 08:00:00');", (payswift_id, payswift_tc_v1, 1))
    cursor.execute("INSERT INTO TermsConditions (website_id, terms_content, version, updated_at) VALUES (?, ?, ?, '2024-09-05 15:30:00');", (payswift_id, payswift_tc_v2, 2))

    # DevPortal Terms
    devportal_tc_v1 = """DevPortal Terms of Service (Version 1.0)
Effective Date: April 1, 2024

1. Open Source Contributions
All code snippets shared in forum posts are released under the MIT Open Source License."""
    cursor.execute("INSERT INTO TermsConditions (website_id, terms_content, version, updated_at) VALUES (?, ?, ?, '2024-04-01 09:00:00');", (devportal_id, devportal_tc_v1, 1))

    print("[*] Seeding ChangeHistory table (with Module 4 classification metadata)...")
    change_events = [
        # Acme Cloud Privacy Changes
        (acme_id, 'Privacy Policy', None, 1, '2024-01-15 10:00:00',
         'Initial Privacy Policy published.', 'general', 'minor', 'Baseline version.', 'confirmed', 'admin', 'Verified baseline publication.'),
        (acme_id, 'Terms & Conditions', None, 1, '2024-01-15 10:00:00',
         'Initial Terms of Service published.', 'general', 'minor', 'Baseline terms.', 'confirmed', 'admin', 'Verified baseline terms.'),
        (acme_id, 'Privacy Policy', 1, 2, '2024-06-01 14:30:00',
         'GDPR & CCPA compliance update with device telemetry and location data.', 'user_rights', 'major',
         'Added collection of IP telemetry, diagnostic cookies, and international data transfer clauses.', 'confirmed', 'admin', 'Audited compliance sections.'),
        (acme_id, 'Terms & Conditions', 1, 2, '2024-07-15 12:00:00',
         'Cancellation notice reduced from 30 to 14 days and liability cap introduced.', 'contract_terms', 'major',
         'Cancellation policy altered; 99.9% uptime SLA and liability limitations added.', 'confirmed', 'admin', 'Legal team reviewed.'),
        (acme_id, 'Privacy Policy', 2, 3, '2024-10-10 09:15:00',
         'AI Model Training opt-in transparency and generative AI data safeguards added.', 'data_collection', 'critical',
         'Clause explicitly restricting customer proprietary files from shared machine learning model training.', 'unreviewed', None, None),

        # SocialPulse Changes
        (social_id, 'Privacy Policy', None, 1, '2024-03-01 11:00:00',
         'Initial SocialPulse Privacy Policy.', 'general', 'minor', 'Baseline social profile policy.', 'confirmed', 'admin', None),
        (social_id, 'Privacy Policy', 1, 2, '2024-08-20 16:45:00',
         'Facial geometry biometrics and real-time ad bidding integration.', 'data_collection', 'critical',
         'Introduces extraction of facial geometry vectors from video uploads and programmatic advertising bidding.', 'unreviewed', None, None),

        # PaySwift Changes
        (payswift_id, 'Privacy Policy', None, 1, '2024-02-10 08:00:00',
         'Initial PCI-DSS merchant privacy statement.', 'security', 'minor', 'Baseline financial telemetry.', 'confirmed', 'admin', None),
        (payswift_id, 'Terms & Conditions', None, 1, '2024-02-10 08:00:00',
         'Standard merchant processing agreement.', 'contract_terms', 'minor', 'Baseline merchant agreement.', 'confirmed', 'admin', None),
        (payswift_id, 'Terms & Conditions', 1, 2, '2024-09-05 15:30:00',
         'Mandatory binding arbitration and class action waiver added.', 'dispute_arbitration', 'critical',
         'Dispute resolution shifted exclusively to American Arbitration Association binding arbitration.', 'unreviewed', None, None),
    ]

    cursor.executemany(
        """INSERT INTO ChangeHistory
           (website_id, change_type, old_version, new_version, change_date,
            summary, category, severity, reasons, review_status, reviewed_by, review_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
        change_events
    )

    print("[*] Seeding Module 5 (Freshness & Notifications)...")
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat(timespec="seconds")
    aging_iso = (now_utc - timedelta(hours=36)).isoformat(timespec="seconds")
    stale_iso = (now_utc - timedelta(hours=96)).isoformat(timespec="seconds")

    freshness_records = [
        ('site-1', 'Acme Cloud Services', now_iso, now_iso, 'checked', None, now_iso),
        ('site-2', 'SocialPulse Media', aging_iso, aging_iso, 'checked', None, now_iso),
        ('site-3', 'PaySwift Gateway', stale_iso, stale_iso, 'checked', None, now_iso),
        ('site-4', 'DevPortal Community', None, None, 'never_checked', None, now_iso),
    ]
    cursor.executemany(
        """INSERT OR REPLACE INTO m5_source_freshness
           (source_id, source_name, last_checked_at, last_changed_at, last_status, last_error, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?);""",
        freshness_records
    )

    notifications = [
        ('site-1', 'Acme Cloud Services', 'policy_changed',
         'Critical Update: Generative AI Data Safeguard',
         'Acme Cloud released Privacy Policy Version 3 with explicit AI training opt-in terms.',
         now_iso, 0, acme_id, 5),
        ('site-2', 'SocialPulse Media', 'policy_changed',
         'Major Policy Update: Facial Geometry Biometrics',
         'SocialPulse added biometric data collection and real-time ad bidding.',
         aging_iso, 0, social_id, 7),
        ('site-3', 'PaySwift Gateway', 'policy_changed',
         'Terms Update: Mandatory Arbitration Clause',
         'PaySwift introduced binding arbitration under American Arbitration Association rules.',
         stale_iso, 1, payswift_id, 10),
    ]
    cursor.executemany(
        """INSERT INTO m5_notifications
           (source_id, source_name, notification_type, title, message, created_at, is_read, website_id, change_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
        notifications
    )

    print("[*] Seeding Scraper Snapshots (Module 1)...")
    snapshots = [
        (acme_id, 'site-1', 'https://acmecloud.io/privacy', 200, 'e367f4dc918a', 2048, 'ptct-scraper/fixtures/demo_privacy_v1.html'),
        (acme_id, 'site-1', 'https://acmecloud.io/privacy', 200, 'e254105f8842', 2410, 'ptct-scraper/fixtures/demo_privacy_v2.html'),
        (social_id, 'site-2', 'https://socialpulse.com/privacy', 200, 'a7199c04901f', 1890, None),
        (payswift_id, 'site-3', 'https://payswift.net/terms', 200, 'bc529f7102ad', 3120, None),
    ]
    cursor.executemany(
        """INSERT INTO ScraperSnapshots
           (website_id, source_id, url, http_status, content_hash, byte_size, file_path)
           VALUES (?, ?, ?, ?, ?, ?, ?);""",
        snapshots
    )

    conn.commit()
    conn.close()

    print("[SUCCESS] Unified sample database populated successfully!")
    print("Demo Accounts:")
    print("  1. Username: admin      | Password: admin123")
    print("  2. Username: john_doe   | Password: password123")


if __name__ == '__main__':
    seed_sample_data()
