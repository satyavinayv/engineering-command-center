"""
Jira integration for a self-hosted (Server/Data Center) instance behind
the company VPN, authenticated with a Personal Access Token as a Bearer
token (Jira Data Center PAT auth — no OAuth app registration needed).

Sync fetches issues via the configured JQL (spec section 7 — never the
whole instance), bounded to a window on first run and using an
`updated >=` watermark as the cursor thereafter.
"""
from typing import Any

import httpx

from app.config import settings
from app.integrations.base import (
    Integration,
    IntegrationAuthError,
    IntegrationConnectionError,
    SyncResult,
)

PAGE_SIZE = 50


class JiraIntegration(Integration):
    key = "jira"
    display_name = "Jira"

    def __init__(self) -> None:
        self.base_url = settings.jira_base_url.rstrip("/")
        self.token = settings.jira_api_token
        self.jql = settings.jira_jql

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
            timeout=15.0,
        )

    def authenticate(self) -> None:
        if not self.is_configured():
            raise IntegrationAuthError("Jira is not configured (missing base URL or PAT)")
        with self._client() as client:
            try:
                resp = client.get("/rest/api/2/myself")
            except httpx.RequestError as exc:
                raise IntegrationConnectionError(f"Could not reach Jira: {exc}") from exc
        if resp.status_code == 401:
            raise IntegrationAuthError("Jira rejected the personal access token")
        resp.raise_for_status()

    def test_connection(self) -> bool:
        try:
            self.authenticate()
            return True
        except (IntegrationAuthError, IntegrationConnectionError):
            return False

    def _search_page(self, jql: str, start_at: int) -> dict:
        with self._client() as client:
            try:
                resp = client.get(
                    "/rest/api/2/search",
                    params={
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": PAGE_SIZE,
                        "fields": "summary,status,priority,issuetype,assignee,reporter,labels,updated",
                    },
                )
            except httpx.RequestError as exc:
                raise IntegrationConnectionError(f"Could not reach Jira: {exc}") from exc
        if resp.status_code == 401:
            raise IntegrationAuthError("Jira rejected the personal access token")
        resp.raise_for_status()
        return resp.json()

    def _sync_from_jql(self, jql: str) -> SyncResult:
        from app.services.jira_sync import persist_issues

        start_at = 0
        total_fetched = 0
        new_count = 0
        updated_count = 0
        latest_updated: str | None = None

        while True:
            page = self._search_page(jql, start_at)
            issues = page.get("issues", [])
            if not issues:
                break

            result = persist_issues(issues, base_url=self.base_url)
            new_count += result["new"]
            updated_count += result["updated"]
            total_fetched += len(issues)

            for issue in issues:
                updated_field = issue.get("fields", {}).get("updated")
                if updated_field and (latest_updated is None or updated_field > latest_updated):
                    latest_updated = updated_field

            start_at += len(issues)
            if start_at >= page.get("total", 0):
                break

        return SyncResult(
            records_fetched=total_fetched,
            records_new=new_count,
            records_updated=updated_count,
            cursor=latest_updated,
        )

    def fetch_initial_data(self, window_days: int | None = None) -> SyncResult:
        jql = self.jql
        if window_days:
            jql = f"({self.jql}) AND updated >= -{window_days}d"
        return self._sync_from_jql(jql)

    def incremental_sync(self, cursor: str | None) -> SyncResult:
        jql = self.jql
        if cursor:
            # Jira JQL date literals need "yyyy-MM-dd HH:mm" - trim the
            # timezone/millis Jira's own `updated` field includes.
            jql = f'({self.jql}) AND updated >= "{cursor[:16].replace("T", " ")}"'
        jql += " ORDER BY updated ASC"
        return self._sync_from_jql(jql)

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        with self._client() as client:
            resp = client.get(f"/rest/api/2/issue/{item_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def search(self, query: str) -> list[dict[str, Any]]:
        """Deterministic search over already-synced Jira issues (not a
        live Jira API call) — spec section 25."""
        from app.database import SessionLocal
        from app.models import JiraIssue

        db = SessionLocal()
        try:
            like = f"%{query}%"
            rows = (
                db.query(JiraIssue)
                .filter((JiraIssue.key.ilike(like)) | (JiraIssue.summary.ilike(like)))
                .limit(25)
                .all()
            )
            return [
                {"key": r.key, "summary": r.summary, "status": r.status, "url": r.url}
                for r in rows
            ]
        finally:
            db.close()
