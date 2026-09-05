"""
Every integration (Gmail, Calendar, Jira, GitLab, OpenSearch, Xray)
implements this same interface. This is the contract that lets the sync
engine, the health page, and the API layer treat all integrations
uniformly, while each one handles its own auth mechanism internally
(Gmail: IMAP + app password; Jira/GitLab: API token; OpenSearch:
host + credentials; etc).

A concrete integration should raise `IntegrationAuthError` on bad
credentials and `IntegrationConnectionError` on network/availability
issues, so the sync engine and health check can distinguish "broken
config" from "service is temporarily down" without guessing.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class IntegrationError(Exception):
    """Base class for integration failures."""


class IntegrationAuthError(IntegrationError):
    pass


class IntegrationConnectionError(IntegrationError):
    pass


@dataclass
class HealthStatus:
    key: str
    connected: bool
    last_sync_at: datetime | None = None
    last_error: str | None = None
    records_synced: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    records_fetched: int
    records_new: int
    records_updated: int
    cursor: str | None = None  # opaque cursor/etag for incremental sync


class Integration(ABC):
    """Abstract base class. key must be a short stable identifier, e.g.
    'gmail', 'jira', 'gitlab', 'opensearch', 'calendar', 'xray'."""

    key: str
    display_name: str

    @abstractmethod
    def authenticate(self) -> None:
        """Establish credentials/session. Raise IntegrationAuthError on
        failure. Must not raise for merely-not-configured-yet state;
        callers check `is_configured()` first."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether required env vars/config are present at all."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Lightweight call to verify the integration is reachable and
        authenticated right now. Used by the health check and by the
        admin 'test connection' UI action."""

    @abstractmethod
    def fetch_initial_data(self, window_days: int | None = None) -> SyncResult:
        """First-time backfill, bounded by a configurable window (do
        NOT pull full history by default — see spec section 5/7)."""

    @abstractmethod
    def incremental_sync(self, cursor: str | None) -> SyncResult:
        """Pull only what's changed since `cursor` (etag/updated_at/
        cursor token, whichever the API supports)."""

    @abstractmethod
    def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Fetch a single item by its source id, for detail views."""

    @abstractmethod
    def search(self, query: str) -> list[dict[str, Any]]:
        """Deterministic keyword/id search within this integration's
        already-synced data (not a live API call)."""

    def health_check(self) -> HealthStatus:
        """Default implementation built on top of test_connection();
        integrations can override for richer detail (rate-limit state,
        latency, etc. per spec section 29)."""
        if not self.is_configured():
            return HealthStatus(key=self.key, connected=False, last_error="Not configured")
        try:
            ok = self.test_connection()
            return HealthStatus(key=self.key, connected=ok)
        except IntegrationError as exc:
            return HealthStatus(key=self.key, connected=False, last_error=str(exc))
