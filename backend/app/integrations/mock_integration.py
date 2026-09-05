"""
Reference implementation of the Integration interface. Used to:
1. Prove the abstraction works end-to-end before any real integration
   (Jira/GitLab/etc.) exists.
2. Serve as a test double in integration tests (per spec section 35 —
   mock Gmail/Jira/GitLab/etc. for realistic API response testing).
"""
from datetime import datetime, timezone
from typing import Any

from app.integrations.base import HealthStatus, Integration, SyncResult


class MockIntegration(Integration):
    key = "mock"
    display_name = "Mock Integration"

    def __init__(self, always_healthy: bool = True) -> None:
        self._always_healthy = always_healthy
        self._items: dict[str, dict[str, Any]] = {
            "MOCK-1": {"id": "MOCK-1", "title": "Example synced item"},
        }

    def is_configured(self) -> bool:
        return True

    def authenticate(self) -> None:
        return None

    def test_connection(self) -> bool:
        return self._always_healthy

    def fetch_initial_data(self, window_days: int | None = None) -> SyncResult:
        return SyncResult(records_fetched=len(self._items), records_new=len(self._items), records_updated=0)

    def incremental_sync(self, cursor: str | None) -> SyncResult:
        return SyncResult(records_fetched=0, records_new=0, records_updated=0, cursor=cursor)

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        return self._items.get(item_id)

    def search(self, query: str) -> list[dict[str, Any]]:
        return [item for item in self._items.values() if query.lower() in item["title"].lower()]

    def health_check(self) -> HealthStatus:
        return HealthStatus(
            key=self.key,
            connected=self._always_healthy,
            last_sync_at=datetime.now(timezone.utc),
            records_synced=len(self._items),
        )
