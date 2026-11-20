import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from policywatch_module5 import (
    FreshnessConfig,
    NotificationFreshnessService
)


class NotificationFreshnessTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = NotificationFreshnessService(
            str(Path(self.temp.name) / "test.db"),
            FreshnessConfig(
                aging_after_hours=24,
                stale_after_hours=72
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_success_is_fresh(self):
        self.service.record_check_success("site-a")
        self.assertEqual(
            self.service.get_freshness("site-a")["freshness"],
            "fresh"
        )

    def test_never_checked(self):
        self.assertEqual(
            self.service.get_freshness("missing")["freshness"],
            "never_checked"
        )

    def test_failure_does_not_create_success(self):
        self.service.record_check_failure("site-a", "network error")
        result = self.service.get_freshness("site-a")
        self.assertEqual(result["freshness"], "never_checked")
        self.assertEqual(result["last_error"], "network error")

    def test_change_creates_notification(self):
        notification_id = self.service.record_change(
            "site-a", "Changed", "Details"
        )
        self.assertGreater(notification_id, 0)
        self.assertEqual(self.service.unread_count(), 1)

        self.assertTrue(
            self.service.mark_notification_read(notification_id)
        )
        self.assertEqual(self.service.unread_count(), 0)

    def test_old_success_is_stale(self):
        old = (
            datetime.now(timezone.utc) - timedelta(hours=80)
        ).isoformat()

        self.service.record_check_success("site-a", checked_at=old)

        self.assertEqual(
            self.service.get_freshness("site-a")["freshness"],
            "stale"
        )


if __name__ == "__main__":
    unittest.main()
