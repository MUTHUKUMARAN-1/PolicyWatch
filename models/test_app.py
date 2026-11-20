"""
test_app.py
Comprehensive test suite verifying all routes, CRUD operations,
data validations, database cascades, and template rendering.
"""

import unittest
from .app import app
from . import database as db
from .sample_data import seed_sample_data


class PolicyTrackerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Re-seed test database with known sample data
        seed_sample_data()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def login(self, username, password):
        return self.client.post('/login', data={
            'identifier': username,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # 1. Test Public Routes
    def test_01_public_routes(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Privacy Policy &amp; Terms Change Tracker', resp.data)

        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'User Login', resp.data)

        resp = self.client.get('/register')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Create User Account', resp.data)

    # 2. Test User Registration
    def test_02_registration(self):
        resp = self.client.post('/register', data={
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'secretpassword',
            'confirm_password': 'secretpassword'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'System Dashboard', resp.data)
        self.assertIn(b'testuser', resp.data)

    # 3. Test Authentication
    def test_03_login_and_logout(self):
        self.logout()
        resp = self.login('admin', 'admin123')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'System Dashboard', resp.data)
        self.assertIn(b'Acme Cloud Services', resp.data)

        # Invalid login
        self.logout()
        resp = self.login('admin', 'wrongpassword')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Invalid username/email or password', resp.data)

    # 4. Test Dashboard
    def test_04_dashboard(self):
        self.login('admin', 'admin123')
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Websites Tracked', resp.data)
        self.assertIn(b'Policy Versions Stored', resp.data)
        self.assertIn(b'Acme Cloud Services', resp.data)

    # 5. Test Website CRUD: Create
    def test_05_create_website(self):
        self.login('admin', 'admin123')
        resp = self.client.post('/websites/add', data={
            'website_name': 'Quantum Compute Labs',
            'website_url': 'https://quantumlabs.tech',
            'initial_policy': 'Initial Quantum Privacy Policy text here.\nNo user data is stored on qubits.',
            'initial_terms': 'Initial Quantum Terms of Service.\nAll quantum cycles are billed per second.'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Quantum Compute Labs', resp.data)
        self.assertIn(b'Version 1', resp.data)

    # 6. Test Website Details View
    def test_06_website_details(self):
        self.login('admin', 'admin123')
        resp = self.client.get('/websites/1')  # Acme Cloud
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Acme Cloud Services', resp.data)
        self.assertIn(b'Privacy Policy', resp.data)
        self.assertIn(b'Terms &amp; Conditions', resp.data)

    # 7. Test Privacy Policy Version Update (CRUD: Update)
    def test_07_update_privacy_policy(self):
        self.login('admin', 'admin123')
        resp = self.client.post('/websites/1/privacy/update', data={
            'policy_content': 'Acme Cloud Privacy Policy (Version 4.0)\nUpdated with strict quantum encryption safeguards.'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Version 4', resp.data)

    # 8. Test Terms & Conditions Version Update (CRUD: Update)
    def test_08_update_terms(self):
        self.login('admin', 'admin123')
        resp = self.client.post('/websites/1/terms/update', data={
            'terms_content': 'Acme Cloud Terms of Service (Version 3.0)\nAdded new high-availability SLA terms.'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Version 3', resp.data)

    # 9. Test History Views
    def test_09_history_views(self):
        self.login('admin', 'admin123')
        # Privacy history
        resp = self.client.get('/websites/1/privacy-history')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Privacy Policy Version History', resp.data)

        # Terms history
        resp = self.client.get('/websites/1/terms-history')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Terms &amp; Conditions Version History', resp.data)

        # Global change history
        resp = self.client.get('/history')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Complete Change Audit History', resp.data)

    # 10. Test Compare Versions (Diff Engine)
    def test_10_diff_comparison(self):
        self.login('admin', 'admin123')
        # Side-by-side mode
        resp = self.client.get('/websites/1/compare?type=policy&v1=1&v2=2&mode=side_by_side')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Side-by-Side Comparison', resp.data)
        self.assertIn(b'Lines Added', resp.data)
        self.assertIn(b'Lines Removed', resp.data)

        # Inline mode
        resp = self.client.get('/websites/1/compare?type=policy&v1=1&v2=2&mode=inline')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Line-by-Line Unified Diff', resp.data)
        self.assertIn(b'diff-line', resp.data)

    # 11. Test Website Edit (CRUD: Update)
    def test_11_edit_website(self):
        self.login('admin', 'admin123')
        resp = self.client.post('/websites/2/edit', data={
            'website_name': 'SocialPulse Global Network',
            'website_url': 'https://socialpulse.com'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'SocialPulse Global Network', resp.data)

    # 12. Test Website Delete (CRUD: Delete with Cascade)
    def test_12_delete_website(self):
        self.login('admin', 'admin123')
        with self.app.app_context():
            # Create a temporary site to delete
            site_id = db.create_website(1, 'Temp Site To Delete', 'https://delete-me.test')
            db.add_privacy_policy(site_id, 'Temp policy')
            db.add_terms_conditions(site_id, 'Temp terms')

            # Delete it
            resp = self.client.post(f'/websites/{site_id}/delete', follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'were deleted', resp.data)

            # Ensure site and associated records are deleted
            deleted_site = db.get_website_by_id(site_id)
            self.assertIsNone(deleted_site)
            self.assertEqual(len(db.get_privacy_policy_history(site_id)), 0)
            self.assertEqual(len(db.get_terms_history(site_id)), 0)
            self.assertEqual(len(db.get_change_history_for_website(site_id)), 0)


if __name__ == '__main__':
    unittest.main()
