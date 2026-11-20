"""
End-to-End System Integration Test Suite for PolicyWatch.
Validates cross-module integration across:
- Module 1: Web Scraping and Snapshots (ptct-scraper bridge)
- Module 2: DBMS and Relational Data Layer (models/database)
- Module 3: Authentication and Session Security (models/app)
- Module 4: Search, Multi-Criteria Filtering, Diff View & Change Review (models/diff_utils & change_detection)
- Module 5: Source Freshness Tracking and Notification Center (policywatch_module5)
"""
import os
import sys
import tempfile
import unittest

# Setup path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

models_dir = os.path.join(ROOT_DIR, 'models')
if models_dir not in sys.path:
    sys.path.insert(0, models_dir)

from models import database as db
from models.app import app
from models import diff_utils
from models import scraper_service
from change_detection.api import detect_changes


class PolicyWatchIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary test database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        db.DATABASE_FILE = self.db_path

        # Initialize schema & upgrades
        db.init_db()
        db.ensure_schema_upgrades()

        # Configure Flask test client
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret-integration'
        self.client = app.test_client()

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except OSError:
            pass

    def test_end_to_end_data_flow(self):
        """
        Full lifecycle test:
        1. Register user & login
        2. Create website
        3. Add policy versions & detect changes
        4. Trigger Module 5 notification & freshness verification
        5. Run Module 4 search & multi-criteria filtering
        6. Verify side-by-side & unified diff generation with NLP classifier
        7. Execute change review workflow
        8. Run scraper offline refresh cycle
        """
        # --- 1. USER REGISTRATION & AUTH (Module 3) ---
        reg_res = self.client.post('/register', data={
            'username': 'tester_compliance',
            'email': 'tester@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)

        # Log in
        login_res = self.client.post('/login', data={
            'username': 'tester_compliance',
            'password': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Dashboard', login_res.data)

        user = db.get_user_by_username('tester_compliance')
        self.assertIsNotNone(user)
        user_id = user['user_id']

        # --- 2. ADD TRACKED WEBSITE (Module 2) ---
        w_id = db.add_website(
            user_id=user_id,
            website_name="Acme Privacy Portal",
            website_url="https://acme.test/privacy",
            domain="acme.test"
        )
        self.assertGreater(w_id, 0)

        site = db.get_website_by_id(w_id, user_id)
        self.assertEqual(site['website_name'], "Acme Privacy Portal")

        # --- 3. ADD VERSIONS & TRIGGER CHANGE DETECTION (Module 2 + change_detection) ---
        v1_text = (
            "We collect your email address for account authentication. "
            "We will never sell or share your personal data with third parties. "
            "Data is stored securely on servers located in the EU."
        )
        _, v1_num = db.add_privacy_policy(w_id, v1_text)
        self.assertEqual(v1_num, 1)

        v2_text = (
            "We collect your email address, phone number, and precise GPS location. "
            "We may share anonymized behavioral data and identifiers with advertising partners. "
            "Data may be transferred and processed in non-EEA jurisdictions."
        )
        _, v2_num = db.add_privacy_policy(w_id, v2_text)
        self.assertEqual(v2_num, 2)

        # Verify change history created with severity and category
        changes = db.get_changes_by_website(w_id)
        self.assertGreaterEqual(len(changes), 1)
        latest_change = changes[0]
        self.assertEqual(latest_change['old_version'], 1)
        self.assertEqual(latest_change['new_version'], 2)
        self.assertIn(latest_change['severity'].lower(), ['major', 'moderate', 'minor', 'none'])

        # --- 4. NOTIFICATIONS & FRESHNESS (Module 5) ---
        # Verify notification was generated for this change
        notifications = db.get_notifications_for_user(user_id)
        self.assertGreaterEqual(len(notifications), 1)
        unread_count = db.get_unread_notification_count(user_id)
        self.assertGreaterEqual(unread_count, 1)

        # Test mark as read
        notif_id = notifications[0]['notification_id']
        db.mark_notification_as_read(notif_id)
        new_unread = db.get_unread_notification_count(user_id)
        self.assertEqual(new_unread, unread_count - 1)

        # Freshness verification
        freshness_list = db.get_all_source_freshness(user_id)
        self.assertGreaterEqual(len(freshness_list), 1)
        summary = db.get_freshness_summary(user_id)
        self.assertIn(summary['fresh'], [0, 1])

        # --- 5. SEARCH & MULTI-CRITERIA FILTERING (Module 4A & 4B) ---
        # Search by query keyword "location"
        search_kw = db.search_records(user_id=user_id, query_str="location")
        self.assertGreaterEqual(search_kw['count'], 1)

        # Search by site_id filter
        search_site = db.search_records(user_id=user_id, site_id=w_id)
        self.assertGreaterEqual(search_site['count'], 1)

        # Search with combined criteria
        search_combined = db.search_records(
            user_id=user_id,
            site_id=w_id,
            doc_type='policy',
            review_status='unreviewed'
        )
        self.assertGreaterEqual(search_combined['count'], 1)

        # Test HTTP route /search
        search_resp = self.client.get(f'/search?q=location&site_id={w_id}')
        self.assertEqual(search_resp.status_code, 200)
        self.assertIn(b'Acme Privacy Portal', search_resp.data)

        # --- 6. DIFF ENGINE & COMPARATOR (Module 4C & 4D) ---
        stats = diff_utils.get_diff_statistics(v1_text, v2_text)
        self.assertGreater(stats['additions'], 0)
        self.assertGreater(stats['deletions'], 0)

        sbs_rows = diff_utils.generate_side_by_side_diff(v1_text, v2_text)
        self.assertGreater(len(sbs_rows), 0)

        inline_html = diff_utils.generate_inline_diff(v1_text, v2_text)
        self.assertIn('diff-add', inline_html)
        self.assertIn('diff-del', inline_html)

        # NLP classification via change_detection
        nlp_rep = detect_changes(v1_text, v2_text, document_id="acme_privacy")
        self.assertGreater(len(nlp_rep.changes), 0)

        # Test HTTP route /compare
        compare_resp = self.client.get(f'/websites/{w_id}/compare?type=policy&v1=1&v2=2')
        self.assertEqual(compare_resp.status_code, 200)
        self.assertIn(b'Side-by-Side Comparison', compare_resp.data)

        # --- 7. CHANGE DETAIL & REVIEW WORKFLOW (Module 4E) ---
        change_id = latest_change['change_id']
        detail_resp = self.client.get(f'/changes/{change_id}')
        self.assertEqual(detail_resp.status_code, 200)
        self.assertIn(b'Review &amp; Audit Workflow', detail_resp.data)

        # Submit a review decision
        review_post = self.client.post(f'/changes/{change_id}/review', data={
            'review_status': 'confirmed',
            'review_notes': 'Verified major tracking clause addition.'
        }, follow_redirects=True)
        self.assertEqual(review_post.status_code, 200)

        updated_change = db.get_change_by_id(change_id, user_id)
        self.assertEqual(updated_change['review_status'], 'confirmed')
        self.assertIn('Verified major tracking', updated_change['review_notes'])

        # --- 8. SCRAPER OFFLINE REFRESH (Module 1) ---
        refresh_res = scraper_service.run_offline_refresh(w_id, user_id)
        self.assertTrue(refresh_res['success'])

        snapshots = db.get_recent_snapshots(limit=10)
        self.assertGreaterEqual(len(snapshots), 1)

        print("\n[+] Full End-to-End Integration Flow Verified Successfully!")


if __name__ == '__main__':
    unittest.main()
