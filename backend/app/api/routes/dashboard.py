"""
Dashboard summary endpoint (new).

One small, fast aggregation over already-synced DB data for the
frontend's single dashboard-load call. Deliberately mirrors the
"never call external APIs live, never send large payloads" rules that
already govern every other route in this app (spec sections 18/36) -
this just consolidates counts that would otherwise take 8+ separate
frontend requests into one.

No email bodies, Jira descriptions, or GitLab diffs are included here
- only counts and the compact ActionItem shape (source/priority/title/
description/url/timestamp/key) that action_engine.py already produces
for exactly this reason.
"""
from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.api.routes.health import health as compute_health
from app.config import settings
from app.database import SessionLocal
from app.models import CalendarEvent, EmailMessage, GitLabMergeRequest, JiraIssue, TestExecution
from app.services.action_engine import get_action_items
from app.services.ai_summary import get_cached_daily_briefing

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_api_key)])

TOP_ACTION_ITEMS_LIMIT = 20


def _now_utc() -> datetime:
    return datetime.utcnow()


@router.get("/summary")
def dashboard_summary() -> dict:
    db = SessionLocal()
    try:
        now = _now_utc()

        # --- Action Required (spec section 15) ---
        action_items = get_action_items(include_p3=False)
        action_required_count = len(action_items)
        top_action_items = [i.to_dict() for i in action_items[:TOP_ACTION_ITEMS_LIMIT]]

        # --- Calendar ---
        next_event = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.start_at >= now)
            .order_by(CalendarEvent.start_at.asc())
            .first()
        )
        pending_rsvp_count = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.is_organizer.is_(False),
                CalendarEvent.my_rsvp_status == "NEEDS-ACTION",
                CalendarEvent.start_at >= now,
            )
            .count()
        )

        # --- Gmail ---
        gmail_action_required_count = (
            db.query(EmailMessage).filter(EmailMessage.action_required.is_(True)).count()
        )
        gmail_unread_count = db.query(EmailMessage).filter(EmailMessage.unread.is_(True)).count()

        # --- Jira ---
        # "active" = not in the done-statuses list (mirrors JIRA_JQL's
        # own exclusion, see settings.jira_done_statuses).
        # "important" = priority is one of the configured P0 priority
        # names (settings.action_p0_jira_priorities) - the same list
        # priority_engine.py already uses to mean P0.
        jira_issues = db.query(JiraIssue.status, JiraIssue.priority).all()
        done = set(settings.jira_done_statuses_list)
        p0_priorities = set(settings.action_p0_jira_priorities_list)
        jira_active_count = sum(1 for status, _ in jira_issues if status.strip().lower() not in done)
        jira_important_count = sum(
            1 for _, priority in jira_issues if priority.strip().lower() in p0_priorities
        )

        # --- GitLab ---
        review_waiting_count = (
            db.query(GitLabMergeRequest)
            .filter(
                GitLabMergeRequest.reviewers.ilike(f"%{settings.gitlab_username}%"),
                GitLabMergeRequest.state == "opened",
            )
            .count()
        )
        failed_pipeline_count = (
            db.query(GitLabMergeRequest)
            .filter(
                GitLabMergeRequest.author_username == settings.gitlab_username,
                GitLabMergeRequest.state == "opened",
                GitLabMergeRequest.computed_state == "PIPELINE_FAILED",
            )
            .count()
        )

        # --- Test automation ---
        # Small dataset at single-user scale (spec section 38) - plain
        # Python counting instead of per-status SQL is simpler and
        # avoids duplicating the FAIL/FAILED normalization logic that
        # already lives in priority_engine.classify_test_execution_priority.
        statuses = [s for (s,) in db.query(TestExecution.status).all()]
        test_fail_count = sum(1 for s in statuses if s and s.strip().upper() in ("FAIL", "FAILED"))
        test_pass_count = sum(1 for s in statuses if s and s.strip().upper() == "PASS")

        # --- AI (availability/cache status only - never the content
        # itself here; GET /api/ai/daily-briefing is where the actual
        # briefing text is fetched, on demand, still non-blocking) ---
        briefing = get_cached_daily_briefing()

        return {
            "generated_at": now.isoformat(),
            "health": {
                "status": compute_health()["status"],
            },
            "action_required": {
                "count": action_required_count,
                "top_items": top_action_items,
            },
            "calendar": {
                "next_event": _serialize_event(next_event) if next_event else None,
                "pending_rsvp_count": pending_rsvp_count,
            },
            "gmail": {
                "action_required_count": gmail_action_required_count,
                "unread_count": gmail_unread_count,
            },
            "jira": {
                "active_count": jira_active_count,
                "important_count": jira_important_count,
            },
            "gitlab": {
                "review_waiting_count": review_waiting_count,
                "failed_pipeline_count": failed_pipeline_count,
            },
            "tests": {
                "fail_count": test_fail_count,
                "pass_count": test_pass_count,
            },
            "ai": {
                "enabled": settings.ai_enabled,
                "available": briefing["available"],
                "cached": briefing["cached"],
                "generated_at": briefing["created_at"],
            },
        }
    finally:
        db.close()


def _serialize_event(event: CalendarEvent) -> dict:
    return {
        "source_uid": event.source_uid,
        "title": event.title,
        "start_at": event.start_at.isoformat() if event.start_at else None,
        "calendar_link": event.calendar_link,
        "my_rsvp_status": event.my_rsvp_status,
    }