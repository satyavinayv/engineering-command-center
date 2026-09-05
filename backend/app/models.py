"""
Phase 1 schema: just enough to register integrations and track sync
health. Later phases append tables here (emails, calendar_events,
jira_issues, gitlab_merge_requests, test_cases, test_executions,
entity_relationships, notifications, actions, ai_summaries, ...) per
docs/ARCHITECTURE.md — we are not building those yet.
"""
import datetime as dt

from sqlalchemy import Boolean, DateTime, Integer, String, Text
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
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
