"""
Read-only GitLab endpoints, always from the local database. `/mine` and
`/to-review` are the two dashboard sections from spec section 8;
`/merge-requests/{source_id}` is the single "MR Detail" view from
section 24 that ties together the MR, its reviewer comments, and any
correlated Jira issues, so the user never has to jump between GitLab and
Jira manually.
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.config import settings
from app.database import SessionLocal
from app.models import EntityRelationship, GitLabComment, GitLabMergeRequest

router = APIRouter(prefix="/api/gitlab", tags=["gitlab"], dependencies=[Depends(require_api_key)])


def _serialize(mr: GitLabMergeRequest) -> dict:
    return {
        "source_id": mr.source_id,
        "iid": mr.iid,
        "project_id": mr.project_id,
        "title": mr.title,
        "author": mr.author_username,
        "source_branch": mr.source_branch,
        "target_branch": mr.target_branch,
        "state": mr.state,
        "computed_state": mr.computed_state,
        "pipeline_status": mr.pipeline_status,
        "approved": mr.approved,
        "approvals_required": mr.approvals_required,
        "approvals_left": mr.approvals_left,
        "reviewers": mr.reviewers.split(",") if mr.reviewers else [],
        "web_url": mr.web_url,
        "updated_at": mr.updated_at.isoformat() if mr.updated_at else None,
    }


@router.get("/merge-requests/mine")
def my_open_merge_requests():
    db = SessionLocal()
    try:
        rows = (
            db.query(GitLabMergeRequest)
            .filter(GitLabMergeRequest.author_username == settings.gitlab_username)
            .filter(GitLabMergeRequest.state == "opened")
            .order_by(GitLabMergeRequest.updated_at.desc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/merge-requests/to-review")
def merge_requests_to_review():
    db = SessionLocal()
    try:
        rows = (
            db.query(GitLabMergeRequest)
            .filter(GitLabMergeRequest.reviewers.ilike(f"%{settings.gitlab_username}%"))
            .filter(GitLabMergeRequest.state == "opened")
            .order_by(GitLabMergeRequest.updated_at.desc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/merge-requests/{source_id}")
def merge_request_detail(source_id: int):
    db = SessionLocal()
    try:
        mr = db.query(GitLabMergeRequest).filter_by(source_id=source_id).one_or_none()
        if not mr:
            return {"error": "not found"}

        comments = (
            db.query(GitLabComment)
            .filter_by(mr_source_id=source_id)
            .order_by(GitLabComment.created_at.desc())
            .all()
        )
        related_jira = (
            db.query(EntityRelationship)
            .filter_by(from_type="gitlab_mr", from_key=str(source_id), to_type="jira_issue")
            .all()
        )

        detail = _serialize(mr)
        detail["comments"] = [
            {
                "author": c.author_username,
                "body": c.body,
                "type": c.comment_type,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ]
        detail["related_jira_issues"] = [r.to_key for r in related_jira]
        return detail
    finally:
        db.close()
