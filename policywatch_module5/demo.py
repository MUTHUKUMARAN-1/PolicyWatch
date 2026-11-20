"""Run: python demo.py"""

from pathlib import Path
from tempfile import TemporaryDirectory

from policywatch_module5 import NotificationFreshnessService

with TemporaryDirectory() as folder:
    service = NotificationFreshnessService(
        str(Path(folder) / "demo.db")
    )

    service.record_check_success("demo-privacy-policy")

    service.record_change(
        "demo-privacy-policy",
        "Policy update detected",
        "The existing change detector reported an updated policy section."
    )

    print(
        "Freshness:",
        service.get_freshness("demo-privacy-policy")["freshness"]
    )

    print("Unread notifications:", service.unread_count())
    print("Notifications:", service.list_notifications())
