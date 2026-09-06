"""
OpenSearch integration. Unlike Jira/GitLab, this doesn't page through
"everything changed since X" - it asks, per known Xray test case, for
the single most recent execution document (spec sections 10, 12).
"Known test cases" = Jira issues already synced whose issue_type is in
OPENSEARCH_TEST_ISSUE_TYPES (default "Test", Xray's standard type name).

Auth: HTTP Basic if username+password are set, otherwise no auth header
at all (some internal, VPN-only ES clusters don't require it).
"""
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.integrations.base import (
    Integration,
    IntegrationAuthError,
    IntegrationConnectionError,
    SyncResult,
)


def build_execution_query(x_ray_id: str, environment: str, window_days: int) -> dict:
    """Same shape as the query you gave me, with one addition: an
    explicit sort by @timestamp desc. Without it, `"size": 1` returns
    an arbitrary matching document, not necessarily the latest one."""
    return {
        "size": 1,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "docvalue_fields": [
            {"field": "test_method"},
            {"field": "test_class"},
            {"field": "x_ray_id"},
        ],
        "_source": {"excludes": []},
        "query": {
            "bool": {
                "filter": [
                    {"match_phrase": {"environment": environment}},
                    {"range": {"@timestamp": {"gte": f"now-{window_days}d", "lte": "now"}}},
                    {
                        "bool": {
                            "should": [{"match_phrase": {"x_ray_id": x_ray_id}}],
                            "minimum_should_match": 1,
                        }
                    },
                ]
            }
        },
    }


class OpenSearchIntegration(Integration):
    key = "opensearch"
    display_name = "OpenSearch"

    def __init__(self) -> None:
        self.host = settings.opensearch_host.rstrip("/")
        self.username = settings.opensearch_username
        self.password = settings.opensearch_password
        self.index_pattern = settings.opensearch_index_pattern
        self.environment = settings.opensearch_environment
        self.window_days = settings.opensearch_window_days
        self.test_issue_types = [
            t.strip() for t in settings.opensearch_test_issue_types.split(",") if t.strip()
        ]

    def is_configured(self) -> bool:
        return bool(self.host)

    def _client(self) -> httpx.Client:
        auth = (self.username, self.password) if self.username and self.password else None
        return httpx.Client(
            base_url=self.host,
            auth=auth,
            verify=settings.opensearch_verify_ssl,
            timeout=15.0,
        )

    def authenticate(self) -> None:
        if not self.is_configured():
            raise IntegrationAuthError("OpenSearch is not configured (missing host)")
        with self._client() as client:
            try:
                resp = client.get("/")
            except httpx.RequestError as exc:
                raise IntegrationConnectionError(f"Could not reach OpenSearch: {exc}") from exc
        if resp.status_code == 401:
            raise IntegrationAuthError("OpenSearch rejected the configured credentials")
        resp.raise_for_status()

    def test_connection(self) -> bool:
        try:
            self.authenticate()
            return True
        except (IntegrationAuthError, IntegrationConnectionError):
            return False

    def _known_test_case_keys(self) -> list[str]:
        from app.database import SessionLocal
        from app.models import JiraIssue

        if not self.test_issue_types:
            return []
        db = SessionLocal()
        try:
            rows = (
                db.query(JiraIssue.key)
                .filter(JiraIssue.issue_type.in_(self.test_issue_types))
                .all()
            )
            return [r[0] for r in rows]
        finally:
            db.close()

    def _query_latest_execution(self, client: httpx.Client, test_case_key: str) -> dict | None:
        query = build_execution_query(test_case_key, self.environment, self.window_days)
        try:
            resp = client.post(f"/{self.index_pattern}/_search", json=query)
        except httpx.RequestError as exc:
            raise IntegrationConnectionError(f"Could not reach OpenSearch: {exc}") from exc
        if resp.status_code == 401:
            raise IntegrationAuthError("OpenSearch rejected the configured credentials")
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        return hits[0] if hits else None

    def _sync_latest_executions(self) -> SyncResult:
        from app.services.opensearch_sync import persist_execution

        test_case_keys = self._known_test_case_keys()
        total_fetched = 0
        new_count = 0
        updated_count = 0

        with self._client() as client:
            for key in test_case_keys:
                hit = self._query_latest_execution(client, key)
                if not hit:
                    continue
                result = persist_execution(hit, test_case_key=key)
                total_fetched += 1
                if result["new"]:
                    new_count += 1
                else:
                    updated_count += 1

        return SyncResult(records_fetched=total_fetched, records_new=new_count, records_updated=updated_count)

    def fetch_initial_data(self, window_days: int | None = None) -> SyncResult:
        return self._sync_latest_executions()

    def incremental_sync(self, cursor: str | None) -> SyncResult:
        # There's no meaningful "cursor" here - we always want the
        # single latest execution per test case, so every sync just
        # re-asks the same question. Cheap because it's one small query
        # per test case, not a full re-index.
        return self._sync_latest_executions()

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        from app.database import SessionLocal
        from app.models import TestExecution

        db = SessionLocal()
        try:
            row = (
                db.query(TestExecution)
                .filter_by(test_case_key=item_id)
                .order_by(TestExecution.executed_at.desc())
                .first()
            )
            if not row:
                return None
            return {
                "test_case_key": row.test_case_key,
                "status": row.status,
                "environment": row.environment,
                "executed_at": row.executed_at.isoformat() if row.executed_at else None,
                "raw_source": json.loads(row.raw_source),
            }
        finally:
            db.close()

    def search(self, query: str) -> list[dict[str, Any]]:
        from app.database import SessionLocal
        from app.models import TestExecution

        db = SessionLocal()
        try:
            like = f"%{query}%"
            rows = (
                db.query(TestExecution)
                .filter(TestExecution.test_case_key.ilike(like))
                .limit(25)
                .all()
            )
            return [{"test_case_key": r.test_case_key, "status": r.status} for r in rows]
        finally:
            db.close()
