"""
Read-only Jira endpoints. Always reads from the local database — never
calls Jira live on a dashboard request (spec section 36/18: dashboard
load must not depend on external API calls).
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.database import SessionLocal
from app.models import JiraIssue

router = APIRouter(prefix="/api/jira", tags=["jira"], dependencies=[Depends(require_api_key)])


def _serialize(issue: JiraIssue) -> dict:
    return {
        "key": issue.key,
        "summary": issue.summary,
        "status": issue.status,
        "priority": issue.priority,
        "issue_type": issue.issue_type,
        "assignee": issue.assignee,
        "reporter": issue.reporter,
        "labels": issue.labels.split(",") if issue.labels else [],
        "url": issue.url,
        "updated_at": issue.raw_updated_at.isoformat() if issue.raw_updated_at else None,
    }


@router.get("/issues")
def list_issues(status: str | None = None):
    db = SessionLocal()
    try:
        query = db.query(JiraIssue)
        if status:
            query = query.filter(JiraIssue.status == status)
        rows = query.order_by(JiraIssue.raw_updated_at.desc()).limit(200).all()
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/issues/{key}")
def get_issue(key: str):
    db = SessionLocal()
    try:
        issue = db.query(JiraIssue).filter_by(key=key).one_or_none()
        if not issue:
            return {"error": "not found"}
        return _serialize(issue)
    finally:
        db.close()
