"""
Unified Action Engine (spec sections 14, 15, 16). Reads already-synced
data from every source's own table - never calls any external API
itself - and produces one sorted, prioritized list. This is the "top
layer" over the data: pure aggregation + the deterministic priority
rules in priority_engine.py, computed on read. At single-user scale
this is fast enough to not need its own persisted table (spec section
38 - don't overengineer).
"""
from dataclasses import dataclass
from datetime import datetime

from app.config import settings
from app.database import SessionLocal
from app.models import CalendarEvent, EmailMessage, GitLabMergeRequest, JiraIssue, TestExecution
from app.services.priority_engine import (
    P3,
    classify_calendar_priority,
    classify_gitlab_mr_priority,
    classify_gmail_priority,
    classify_jira_priority,
    classify_test_execution_priority,
)

_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass
class ActionItem:
    source: str  # "gitlab" | "jira" | "calendar" | "gmail" | "tests"
    priority: str
    title: str
    description: str
    url: str | None
    timestamp: datetime | None
    key: str  # stable id for dedup/frontend keys

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "key": self.key,
        }


def _gitlab_items() -> list[ActionItem]:
    db = SessionLocal()
    try:
        items = []
        mine = (
            db.query(GitLabMergeRequest)
            .filter(
                GitLabMergeRequest.author_username == settings.gitlab_username,
                GitLabMergeRequest.state == "opened",
            )
            .all()
        )
        for mr in mine:
            priority = classify_gitlab_mr_priority(mr.computed_state, is_mine=True)
            if not priority:
                continue
            reason = (
                "Pipeline is failing"
                if mr.computed_state == "PIPELINE_FAILED"
                else "A reviewer is waiting on your response"
            )
            items.append(
                ActionItem("gitlab", priority, mr.title, reason, mr.web_url, mr.updated_at, f"gitlab-mr-{mr.source_id}")
            )

        to_review = (
            db.query(GitLabMergeRequest)
            .filter(
                GitLabMergeRequest.reviewers.ilike(f"%{settings.gitlab_username}%"),
                GitLabMergeRequest.state == "opened",
            )
            .all()
        )
        for mr in to_review:
            priority = classify_gitlab_mr_priority(mr.computed_state, is_mine=False)
            if not priority:
                continue
            items.append(
                ActionItem(
                    "gitlab", priority, mr.title, f"Review requested by {mr.author_username}",
                    mr.web_url, mr.updated_at, f"gitlab-mr-{mr.source_id}-review",
                )
            )
        return items
    finally:
        db.close()


def _jira_items() -> list[ActionItem]:
    db = SessionLocal()
    try:
        items = []
        for issue in db.query(JiraIssue).all():
            priority = classify_jira_priority(
                issue.status,
                issue.priority,
                issue.reporter,
                issue.issue_type,
                settings.jira_done_statuses_list,
                settings.action_p0_jira_priorities_list,
            )
            if not priority:
                continue
            items.append(
                ActionItem(
                    "jira", priority, f"{issue.key}: {issue.summary}", f"Status: {issue.status}",
                    issue.url, issue.raw_updated_at, f"jira-{issue.key}",
                )
            )
        return items
    finally:
        db.close()


def _calendar_items() -> list[ActionItem]:
    db = SessionLocal()
    try:
        items = []
        now = datetime.utcnow()
        for event in db.query(CalendarEvent).filter(CalendarEvent.start_at >= now).all():
            priority = classify_calendar_priority(event.is_organizer, event.my_rsvp_status, event.start_at, now)
            if not priority:
                continue
            items.append(
                ActionItem(
                    "calendar", priority, f"RSVP needed: {event.title}",
                    f"Organizer: {event.organizer_email or 'unknown'}",
                    event.calendar_link, event.start_at, f"calendar-{event.source_uid}",
                )
            )
        return items
    finally:
        db.close()


def _gmail_items() -> list[ActionItem]:
    db = SessionLocal()
    try:
        items = []
        for msg in db.query(EmailMessage).filter(EmailMessage.action_required.is_(True)).all():
            priority = classify_gmail_priority(msg.action_required, msg.from_important_sender)
            if not priority:
                continue
            items.append(
                ActionItem(
                    "gmail", priority, msg.subject or "(no subject)", f"From {msg.from_addr}",
                    None, msg.received_at, f"gmail-{msg.message_id}",
                )
            )
        return items
    finally:
        db.close()


def _test_items() -> list[ActionItem]:
    db = SessionLocal()
    try:
        items = []
        for execution in db.query(TestExecution).all():
            priority = classify_test_execution_priority(execution.status)
            if not priority:
                continue
            items.append(
                ActionItem(
                    "tests", priority, f"Automation failing: {execution.test_case_key}",
                    f"Environment: {execution.environment}",
                    execution.opensearch_url or None, execution.executed_at, f"test-{execution.test_case_key}",
                )
            )
        return items
    finally:
        db.close()


def get_action_items(include_p3: bool = False) -> list[ActionItem]:
    items = _gitlab_items() + _jira_items() + _calendar_items() + _gmail_items() + _test_items()
    if not include_p3:
        items = [i for i in items if i.priority != P3]
    items.sort(
        key=lambda i: (
            _PRIORITY_ORDER.get(i.priority, 9),
            -(i.timestamp.timestamp() if i.timestamp else 0),
        )
    )
    return items