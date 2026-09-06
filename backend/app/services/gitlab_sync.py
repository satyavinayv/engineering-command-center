"""
Persists a single enriched GitLab MR payload (as built by
GitLabIntegration._fetch_mr_detail) into gitlab_merge_requests,
gitlab_comments and gitlab_pipelines, deduping by GitLab's own source
ids. Then runs the deterministic state machine, comment classification,
and Jira correlation on it — all before this function returns, so
downstream reads always see fully-processed data (never partially
computed state).
"""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import GitLabComment, GitLabMergeRequest, GitLabPipeline
from app.services.correlation import correlate_merge_request
from app.services.mr_state import compute_mr_state
from app.services.reviewer_detection import classify_comment


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def persist_merge_request(mr: dict, project_id: str, base_url: str) -> dict:
    db = SessionLocal()
    try:
        computed_state = compute_mr_state(mr)
        approvals = mr.get("_approvals") or {}
        pipelines = mr.get("_pipelines") or []
        latest_pipeline = pipelines[0] if pipelines else None
        reviewers_csv = ",".join(r.get("username", "") for r in (mr.get("reviewers") or []))

        existing = db.query(GitLabMergeRequest).filter_by(source_id=mr["id"]).one_or_none()
        is_new = existing is None

        values = dict(
            project_id=int(project_id) if str(project_id).isdigit() else 0,
            iid=mr.get("iid", 0),
            title=mr.get("title", ""),
            author_username=(mr.get("author") or {}).get("username", ""),
            source_branch=mr.get("source_branch", ""),
            target_branch=mr.get("target_branch", ""),
            state=mr.get("state", ""),
            draft=bool(mr.get("draft") or mr.get("work_in_progress")),
            web_url=mr.get("web_url", ""),
            pipeline_status=latest_pipeline.get("status") if latest_pipeline else None,
            approved=bool(approvals.get("approved")),
            approvals_required=approvals.get("approvals_required") or 0,
            approvals_left=approvals.get("approvals_left") or 0,
            has_unresolved_discussions=bool(mr.get("has_unresolved_discussions")),
            reviewers=reviewers_csv,
            computed_state=computed_state,
            updated_at=_parse_dt(mr.get("updated_at")),
            last_synced_at=datetime.now(timezone.utc),
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            existing = GitLabMergeRequest(source_id=mr["id"], **values)
            db.add(existing)
        db.flush()

        for note in mr.get("_notes") or []:
            note_existing = db.query(GitLabComment).filter_by(source_id=note["id"]).one_or_none()
            comment_values = dict(
                mr_source_id=mr["id"],
                author_username=(note.get("author") or {}).get("username", ""),
                body=note.get("body", ""),
                is_system=bool(note.get("system")),
                comment_type=classify_comment(note, mr),
                created_at=_parse_dt(note.get("created_at")),
                last_synced_at=datetime.now(timezone.utc),
            )
            if note_existing:
                for k, v in comment_values.items():
                    setattr(note_existing, k, v)
            else:
                db.add(GitLabComment(source_id=note["id"], **comment_values))

        for pipeline in pipelines:
            pipeline_existing = db.query(GitLabPipeline).filter_by(source_id=pipeline["id"]).one_or_none()
            pipeline_values = dict(
                mr_source_id=mr["id"],
                status=pipeline.get("status", ""),
                web_url=pipeline.get("web_url", ""),
                created_at=_parse_dt(pipeline.get("created_at")),
            )
            if pipeline_existing:
                for k, v in pipeline_values.items():
                    setattr(pipeline_existing, k, v)
            else:
                db.add(GitLabPipeline(source_id=pipeline["id"], **pipeline_values))

        db.commit()
    finally:
        db.close()

    correlate_merge_request(mr, base_url=base_url)
    return {"new": is_new}
