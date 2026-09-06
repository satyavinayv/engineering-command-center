"""
Persists Jira search-API results into the jira_issues table, deduping by
issue key so re-syncing never creates duplicates (spec section 21).
"""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import JiraIssue


def _parse_jira_dt(value: str | None):
    if not value:
        return None
    try:
        # Jira returns e.g. "2026-09-05T10:15:00.000+0000"
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def persist_issues(issues: list[dict], base_url: str) -> dict:
    db = SessionLocal()
    new_count = 0
    updated_count = 0
    try:
        for issue in issues:
            key = issue["key"]
            fields = issue.get("fields", {})
            existing = db.query(JiraIssue).filter_by(key=key).one_or_none()

            values = dict(
                source_id=str(issue.get("id", "")),
                key=key,
                summary=fields.get("summary") or "",
                status=(fields.get("status") or {}).get("name") or "",
                priority=(fields.get("priority") or {}).get("name") or "",
                issue_type=(fields.get("issuetype") or {}).get("name") or "",
                assignee=(fields.get("assignee") or {}).get("displayName"),
                reporter=(fields.get("reporter") or {}).get("displayName"),
                labels=",".join(fields.get("labels") or []),
                url=f"{base_url}/browse/{key}",
                raw_updated_at=_parse_jira_dt(fields.get("updated")),
                last_synced_at=datetime.now(timezone.utc),
            )

            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
                updated_count += 1
            else:
                db.add(JiraIssue(**values))
                new_count += 1

        db.commit()
    finally:
        db.close()

    return {"new": new_count, "updated": updated_count}
