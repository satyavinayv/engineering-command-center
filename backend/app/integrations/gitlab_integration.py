"""
GitLab integration for a self-hosted instance behind the company VPN,
authenticated with a Personal Access Token via the PRIVATE-TOKEN header.

Each MR is fetched with its notes, approvals and pipelines in the same
pass so persist_merge_request can compute deterministic state,
comment classification, and Jira correlation all at once (spec sections
8, 9, 11).
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


class GitLabIntegration(Integration):
    key = "gitlab"
    display_name = "GitLab"

    def __init__(self) -> None:
        self.base_url = settings.gitlab_base_url.rstrip("/")
        self.token = settings.gitlab_personal_access_token
        self.project_ids = [p.strip() for p in settings.gitlab_project_ids.split(",") if p.strip()]
        self.username = settings.gitlab_username

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token and self.project_ids)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=f"{self.base_url}/api/v4",
            headers={"PRIVATE-TOKEN": self.token},
            timeout=15.0,
        )

    def authenticate(self) -> None:
        if not self.is_configured():
            raise IntegrationAuthError(
                "GitLab is not configured (missing base URL, PAT, or project ids)"
            )
        with self._client() as client:
            try:
                resp = client.get("/user")
            except httpx.RequestError as exc:
                raise IntegrationConnectionError(f"Could not reach GitLab: {exc}") from exc
        if resp.status_code == 401:
            raise IntegrationAuthError("GitLab rejected the personal access token")
        resp.raise_for_status()

    def test_connection(self) -> bool:
        try:
            self.authenticate()
            return True
        except (IntegrationAuthError, IntegrationConnectionError):
            return False

    def _fetch_mr_detail(self, client: httpx.Client, project_id: str, iid: int) -> dict:
        mr_resp = client.get(f"/projects/{project_id}/merge_requests/{iid}")
        mr_resp.raise_for_status()
        mr = mr_resp.json()

        notes_resp = client.get(
            f"/projects/{project_id}/merge_requests/{iid}/notes", params={"per_page": 100}
        )
        mr["_notes"] = notes_resp.json() if notes_resp.status_code == 200 else []

        approvals_resp = client.get(f"/projects/{project_id}/merge_requests/{iid}/approvals")
        mr["_approvals"] = approvals_resp.json() if approvals_resp.status_code == 200 else {}

        pipelines_resp = client.get(f"/projects/{project_id}/merge_requests/{iid}/pipelines")
        pipelines = pipelines_resp.json() if pipelines_resp.status_code == 200 else []
        # Most recent first, matching what the state machine expects.
        mr["_pipelines"] = sorted(pipelines, key=lambda p: p.get("created_at", ""), reverse=True)

        return mr

    def _sync_all_projects(self, updated_after: str | None) -> SyncResult:
        from app.services.gitlab_sync import persist_merge_request

        total_fetched = 0
        new_count = 0
        updated_count = 0
        latest_updated = updated_after

        with self._client() as client:
            for project_id in self.project_ids:
                params: dict[str, Any] = {
                    "state": "all",
                    "scope": "all",
                    "per_page": 50,
                    "order_by": "updated_at",
                    "sort": "desc",
                }
                if updated_after:
                    params["updated_after"] = updated_after

                try:
                    resp = client.get(f"/projects/{project_id}/merge_requests", params=params)
                except httpx.RequestError as exc:
                    raise IntegrationConnectionError(f"Could not reach GitLab: {exc}") from exc
                if resp.status_code == 401:
                    raise IntegrationAuthError("GitLab rejected the personal access token")
                resp.raise_for_status()

                for mr_summary in resp.json():
                    detail = self._fetch_mr_detail(client, project_id, mr_summary["iid"])
                    result = persist_merge_request(detail, project_id=project_id, base_url=self.base_url)
                    total_fetched += 1
                    if result["new"]:
                        new_count += 1
                    else:
                        updated_count += 1
                    if not latest_updated or mr_summary["updated_at"] > latest_updated:
                        latest_updated = mr_summary["updated_at"]

        return SyncResult(
            records_fetched=total_fetched,
            records_new=new_count,
            records_updated=updated_count,
            cursor=latest_updated,
        )

    def fetch_initial_data(self, window_days: int | None = None) -> SyncResult:
        return self._sync_all_projects(updated_after=None)

    def incremental_sync(self, cursor: str | None) -> SyncResult:
        return self._sync_all_projects(updated_after=cursor)

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        from app.database import SessionLocal
        from app.models import GitLabMergeRequest

        db = SessionLocal()
        try:
            mr = db.query(GitLabMergeRequest).filter_by(source_id=int(item_id)).one_or_none()
            if not mr:
                return None
            return {
                "source_id": mr.source_id,
                "title": mr.title,
                "state": mr.state,
                "computed_state": mr.computed_state,
                "web_url": mr.web_url,
            }
        finally:
            db.close()

    def search(self, query: str) -> list[dict[str, Any]]:
        from app.database import SessionLocal
        from app.models import GitLabMergeRequest

        db = SessionLocal()
        try:
            like = f"%{query}%"
            rows = (
                db.query(GitLabMergeRequest)
                .filter(GitLabMergeRequest.title.ilike(like))
                .limit(25)
                .all()
            )
            return [{"title": r.title, "web_url": r.web_url, "state": r.computed_state} for r in rows]
        finally:
            db.close()
