"""
sample_data.py
Populates tracker.db with realistic sample data for testing and demonstration.
Includes sample users, websites, multi-version privacy policies, terms & conditions,
and change history logs.
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash
from database import init_db, DATABASE_FILE

def seed_sample_data():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Clear existing tables in reverse order of foreign key dependency
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

    social_pp_v2 = """SocialPulse Privacy Policy (Version 2.0)
Effective Date: August 20, 2024

1. Personal Information Collected:
- Profile name, handle, email address, and avatar image.
- Posts, comments, likes, and social interactions.
- Device advertising identifiers (IDFA, AAID) and approximate geographic location.

2. Usage and Advertising:
- Used to power your social feed and social graph.
- Used to personalize sponsored content and relevant advertising banners.
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
Merchants are assessed a $15 fee per disputed chargeback unless covered by PaySwift Dispute Shield protection."""

    cursor.execute("INSERT INTO TermsConditions (website_id, terms_content, version, updated_at) VALUES (?, ?, ?, '2024-02-10 08:00:00');", (payswift_id, payswift_tc_v1, 1))
    cursor.execute("INSERT INTO TermsConditions (website_id, terms_content, version, updated_at) VALUES (?, ?, ?, '2024-09-05 15:30:00');", (payswift_id, payswift_tc_v2, 2))

    print("[*] Seeding ChangeHistory table...")
    change_events = [
        # Acme Cloud Privacy Changes
        (acme_id, 'Privacy Policy', None, 1, '2024-01-15 10:00:00'),
        (acme_id, 'Terms & Conditions', None, 1, '2024-01-15 10:00:00'),
        (acme_id, 'Privacy Policy', 1, 2, '2024-06-01 14:30:00'),
        (acme_id, 'Terms & Conditions', 1, 2, '2024-07-15 12:00:00'),
        (acme_id, 'Privacy Policy', 2, 3, '2024-10-10 09:15:00'),

        # SocialPulse Changes
        (social_id, 'Privacy Policy', None, 1, '2024-03-01 11:00:00'),
        (social_id, 'Privacy Policy', 1, 2, '2024-08-20 16:45:00'),

        # PaySwift Changes
        (payswift_id, 'Privacy Policy', None, 1, '2024-02-10 08:00:00'),
        (payswift_id, 'Terms & Conditions', None, 1, '2024-02-10 08:00:00'),
        (payswift_id, 'Terms & Conditions', 1, 2, '2024-09-05 15:30:00'),
    ]

    cursor.executemany(
        """INSERT INTO ChangeHistory (website_id, change_type, old_version, new_version, change_date)
           VALUES (?, ?, ?, ?, ?);""",
        change_events
    )

    conn.commit()
    conn.close()

    print("[SUCCESS] Sample database populated successfully!")
    print("Demo Accounts:")
    print("  1. Username: admin      | Password: admin123")
    print("  2. Username: john_doe   | Password: password123")

if __name__ == '__main__':
    seed_sample_data()
