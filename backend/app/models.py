"""
Phase 1 added: users, integrations, sync_status.
Phase 2 adds: jira_issues, jira_comments, gitlab_merge_requests,
gitlab_comments, gitlab_pipelines, entity_relationships.
Later phases still to come: emails, calendar_events, test_cases,
test_executions, notifications, actions, ai_summaries,
ai_classifications — per docs/ARCHITECTURE.md.
"""
import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Integration(Base):
    """One row per integration type (gmail, calendar, jira, gitlab,
    opensearch). Tracks whether it's enabled and its config reference —
    not the credentials themselves, which stay in env vars/secrets."""

    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)  # e.g. "gitlab"
    display_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class SyncStatus(Base):
    """Deterministic health/status record per integration. This is the
    source of truth for the /health endpoint and the future 'System
    Health' page (spec section 29)."""

    __tablename__ = "sync_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_key: Mapped[str] = mapped_column(String(50), unique=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    # Opaque incremental-sync cursor (etag / updated_at watermark / page
    # token — whatever the source API supports). Never re-fetch full
    # history once this is set.
    cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


# ---------------------------------------------------------------------
# Phase 2: Jira
# ---------------------------------------------------------------------


class JiraIssue(Base):
    __tablename__ = "jira_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(50))  # Jira's internal issue id
    key: Mapped[str] = mapped_column(String(50), unique=True)  # e.g. QA-1234
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(100), default="")
    priority: Mapped[str] = mapped_column(String(50), default="")
    issue_type: Mapped[str] = mapped_column(String(50), default="")
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    labels: Mapped[str] = mapped_column(String(500), default="")  # comma-separated
    url: Mapped[str] = mapped_column(String(500), default="")
    raw_updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class JiraComment(Base):
    __tablename__ = "jira_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(50), unique=True)
    jira_issue_key: Mapped[str] = mapped_column(String(50))
    author: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Phase 2: GitLab
# ---------------------------------------------------------------------


class GitLabMergeRequest(Base):
    __tablename__ = "gitlab_merge_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, unique=True)  # GitLab global MR id
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    iid: Mapped[int] = mapped_column(Integer, default=0)  # project-scoped id (used in URLs)
    title: Mapped[str] = mapped_column(String(500), default="")
    author_username: Mapped[str] = mapped_column(String(255), default="")
    source_branch: Mapped[str] = mapped_column(String(255), default="")
    target_branch: Mapped[str] = mapped_column(String(255), default="")
    state: Mapped[str] = mapped_column(String(50), default="")  # opened/closed/merged (GitLab's own)
    draft: Mapped[bool] = mapped_column(Boolean, default=False)
    web_url: Mapped[str] = mapped_column(String(500), default="")
    pipeline_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approvals_required: Mapped[int] = mapped_column(Integer, default=0)
    approvals_left: Mapped[int] = mapped_column(Integer, default=0)
    has_unresolved_discussions: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewers: Mapped[str] = mapped_column(String(500), default="")  # comma-separated usernames
    # Deterministic state machine output (section 9 of the spec) — never
    # AI-derived. See app/services/mr_state.py.
    computed_state: Mapped[str] = mapped_column(String(50), default="OPEN")
    updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class GitLabComment(Base):
    __tablename__ = "gitlab_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, unique=True)  # GitLab note id
    mr_source_id: Mapped[int] = mapped_column(Integer)
    author_username: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # REVIEWER_COMMENT / AUTHOR_COMMENT / BOT_COMMENT / SYSTEM_COMMENT /
    # GENERAL_COMMENT — see app/services/reviewer_detection.py
    comment_type: Mapped[str] = mapped_column(String(30), default="GENERAL_COMMENT")
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class GitLabPipeline(Base):
    __tablename__ = "gitlab_pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, unique=True)
    mr_source_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="")
    web_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------
# Cross-system correlation (spec sections 11, 22)
# ---------------------------------------------------------------------


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_type: Mapped[str] = mapped_column(String(30))  # e.g. "gitlab_mr"
    from_key: Mapped[str] = mapped_column(String(100))  # e.g. GitLab MR source_id as string
    to_type: Mapped[str] = mapped_column(String(30))  # e.g. "jira_issue"
    to_key: Mapped[str] = mapped_column(String(100))  # e.g. "QA-1234"
    relationship_type: Mapped[str] = mapped_column(String(30), default="mentions")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    # "deterministic" always for Phase 2/3. Reserved for "ai" in Phase 7
    # correlation-fallback cases — must always be shown with confidence
    # and never treated as confirmed fact (spec section 11/27).
    source: Mapped[str] = mapped_column(String(20), default="deterministic")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Phase 3: OpenSearch / test execution results
# ---------------------------------------------------------------------


class TestExecution(Base):
    """Latest-known execution for a given Xray test case (Jira issue key
    of a "Test"-type issue). One row per OpenSearch document; re-synced
    on every OpenSearch sync interval since the query always asks for
    the single most recent execution per test case (spec sections 10,
    12, 13)."""

    __tablename__ = "test_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_doc_id: Mapped[str] = mapped_column(String(255), unique=True)  # OpenSearch _id
    test_case_key: Mapped[str] = mapped_column(String(50))  # e.g. TEST-9876
    environment: Mapped[str] = mapped_column(String(50), default="")
    # Best-effort PASS/FAIL/etc extraction using settings.opensearch_status_field.
    # Null until that field name is confirmed - see docs/PHASES.md.
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    test_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    test_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    executed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # Full _source JSON, so nothing is lost even if our field-name
    # guesses above are wrong - this is always available as ground truth
    # (spec section 13: raw failure info must always be displayed).
    raw_source: Mapped[str] = mapped_column(Text, default="{}")
    opensearch_url: Mapped[str] = mapped_column(String(1000), default="")
    last_synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Phase 4: Calendar (ICS import — no live Google API, see
# app/integrations/calendar_integration.py for why)
# ---------------------------------------------------------------------


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_uid: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    start_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str] = mapped_column(String(500), default="")
    organizer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_organizer: Mapped[bool] = mapped_column(Boolean, default=False)
    my_rsvp_status: Mapped[str] = mapped_column(String(20), default="NEEDS-ACTION")
    attendees: Mapped[str] = mapped_column(Text, default="")
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    calendar_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    importance: Mapped[str] = mapped_column(String(20), default="NORMAL")
    importance_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_ics: Mapped[str] = mapped_column(Text, default="")
    last_synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

# ---------------------------------------------------------------------
# Phase 5: Gmail (IMAP + App Password — no OAuth, see
# app/integrations/gmail_integration.py)
# ---------------------------------------------------------------------

class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(998), unique=True)
    folder: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(998), default="")
    from_addr: Mapped[str] = mapped_column(String(500), default="")
    to_addrs: Mapped[str] = mapped_column(String(1000), default="")
    cc_addrs: Mapped[str] = mapped_column(String(1000), default="")
    unread: Mapped[bool] = mapped_column(Boolean, default=True)
    is_addressed_to_me: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cc: Mapped[bool] = mapped_column(Boolean, default=False)
    from_important_sender: Mapped[bool] = mapped_column(Boolean, default=False)
    related_jira_keys: Mapped[str] = mapped_column(String(500), default="")
    related_gitlab_refs: Mapped[str] = mapped_column(String(50), default="")
    action_required: Mapped[bool] = mapped_column(Boolean, default=False)
    snippet: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    last_synced_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow
    )
