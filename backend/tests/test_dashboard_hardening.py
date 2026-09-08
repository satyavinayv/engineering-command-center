"""
Tests for the dashboard-hardening changes: action/gmail limits, ICS
filename sanitization, non-blocking AI briefing, and the new
/api/dashboard/summary aggregation.

Follows the same isolation pattern as test_health_endpoint.py - swap
the integration registry to avoid depending on real credentials/network
- and reuses the app's own SessionLocal/models so these tests exercise
the real DB path (SQLite, per DATABASE_URL) rather than mocking it out,
consistent with how the rest of this test suite works.
"""
import sys
import types

# icalendar isn't guaranteed to be installed in every environment these
# tests run in (see test_calendar_importance.py's precedent) - stub it
# if missing so a plain `pytest` run doesn't hard-fail on collection.
try:
    import icalendar  # noqa: F401
except ImportError:
    sys.modules["icalendar"] = types.SimpleNamespace(Calendar=object)

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import AISummary, EmailMessage

API_HEADERS = {"X-API-Key": settings.api_key}


def _client():
    return TestClient(app)


# ---------------------------------------------------------------------
# Action limit
# ---------------------------------------------------------------------


def test_action_required_default_limit_is_20():
    with _client() as c:
        resp = c.get("/api/actions/required", headers=API_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) <= 20


def test_action_required_respects_explicit_limit():
    with _client() as c:
        resp = c.get("/api/actions/required?limit=3", headers=API_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) <= 3


def test_action_required_rejects_limit_above_max():
    with _client() as c:
        resp = c.get("/api/actions/required?limit=500", headers=API_HEADERS)
    assert resp.status_code == 422


def test_action_required_rejects_zero_or_negative_limit():
    with _client() as c:
        resp = c.get("/api/actions/required?limit=0", headers=API_HEADERS)
    assert resp.status_code == 422


def test_actions_feed_still_available_and_unbounded_by_default():
    """The full feed endpoint must keep working - it's explicitly not
    the dashboard payload, so it isn't limited the same way."""
    with _client() as c:
        resp = c.get("/api/actions/feed", headers=API_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------
# Gmail limits
# ---------------------------------------------------------------------


def test_gmail_messages_default_limit_is_20():
    with _client() as c:
        resp = c.get("/api/gmail/messages", headers=API_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) <= 20


def test_gmail_unread_default_limit_is_20():
    with _client() as c:
        resp = c.get("/api/gmail/unread", headers=API_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) <= 20


def test_gmail_action_required_default_limit_is_20():
    with _client() as c:
        resp = c.get("/api/gmail/action-required", headers=API_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) <= 20


def test_gmail_unread_rejects_limit_above_max():
    with _client() as c:
        resp = c.get("/api/gmail/unread?limit=1000", headers=API_HEADERS)
    assert resp.status_code == 422


def test_gmail_messages_respects_explicit_small_limit():
    with _client() as c:
        resp = c.get("/api/gmail/messages?limit=2", headers=API_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) <= 2


# ---------------------------------------------------------------------
# Calendar ICS filename sanitization + upload size
# ---------------------------------------------------------------------

MINIMAL_ICS = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"


def test_ics_upload_sanitizes_path_traversal_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "calendar_ics_import_dir", str(tmp_path))

    with _client() as c:
        resp = c.post(
            "/api/calendar/import",
            headers=API_HEADERS,
            files={"file": ("../../evil.ics", MINIMAL_ICS, "text/calendar")},
        )

    assert resp.status_code == 200

    # The traversal target (one level above tmp_path) must not exist.
    assert not (tmp_path.parent / "evil.ics").exists()

    # A sanitized file (basename only, no path separators) should have
    # landed inside tmp_path.
    written = list(tmp_path.glob("*evil.ics"))
    assert len(written) == 1
    assert "/" not in written[0].name.replace(str(tmp_path), "")
    assert ".." not in written[0].name


def test_ics_upload_rejects_oversized_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "calendar_ics_import_dir", str(tmp_path))

    from app.api.routes import calendar_api

    monkeypatch.setattr(calendar_api, "MAX_ICS_UPLOAD_BYTES", 10)  # tiny, for the test

    with _client() as c:
        resp = c.post(
            "/api/calendar/import",
            headers=API_HEADERS,
            files={"file": ("big.ics", MINIMAL_ICS, "text/calendar")},
        )

    assert resp.status_code == 413


def test_ics_upload_still_rejects_non_ics_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "calendar_ics_import_dir", str(tmp_path))

    with _client() as c:
        resp = c.post(
            "/api/calendar/import",
            headers=API_HEADERS,
            files={"file": ("not-a-calendar.txt", b"hello", "text/plain")},
        )

    assert resp.status_code == 400


# ---------------------------------------------------------------------
# AI daily briefing must never block/generate on GET when uncached
# ---------------------------------------------------------------------


@pytest.fixture
def no_cached_briefing():
    """Ensure there is no daily_briefing row, then clean up anything
    this test adds - other tests / manual runs may have left one
    behind in the shared local sqlite file."""
    db = SessionLocal()
    try:
        db.query(AISummary).filter(AISummary.kind == "daily_briefing").delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AISummary).filter(AISummary.kind == "daily_briefing").delete()
        db.commit()
    finally:
        db.close()


def test_daily_briefing_get_returns_unavailable_when_no_cache(no_cached_briefing, monkeypatch):
    # If the GET path ever falls through to generation, this provider
    # will raise and fail the test loudly instead of silently passing.
    def _boom(*args, **kwargs):
        raise AssertionError("GET /api/ai/daily-briefing must never call the AI provider")

    monkeypatch.setattr(
        "app.services.ai_summary.get_ai_provider", lambda: types.SimpleNamespace(generate=_boom)
    )

    with _client() as c:
        resp = c.get("/api/ai/daily-briefing", headers=API_HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["content"] is None
    assert body["cached"] is False


def test_daily_briefing_get_preserves_ai_disabled_behavior(no_cached_briefing, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    with _client() as c:
        resp = c.get("/api/ai/daily-briefing", headers=API_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_daily_briefing_regenerate_still_works_explicitly(no_cached_briefing, monkeypatch):
    """POST /regenerate is the one path allowed to generate - confirms
    we didn't break that while making GET non-blocking."""
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_provider", "mock")

    with _client() as c:
        resp = c.post("/api/ai/daily-briefing/regenerate", headers=API_HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["content"] is not None


# ---------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------


def test_dashboard_summary_shape_and_status():
    with _client() as c:
        resp = c.get("/api/dashboard/summary", headers=API_HEADERS)

    assert resp.status_code == 200
    body = resp.json()

    assert "health" in body and "status" in body["health"]
    assert "action_required" in body
    assert "count" in body["action_required"]
    assert "top_items" in body["action_required"]
    assert len(body["action_required"]["top_items"]) <= 20

    assert "calendar" in body
    assert "next_event" in body["calendar"]
    assert "pending_rsvp_count" in body["calendar"]

    assert "gmail" in body
    assert "action_required_count" in body["gmail"]
    assert "unread_count" in body["gmail"]

    assert "jira" in body
    assert "active_count" in body["jira"]
    assert "important_count" in body["jira"]

    assert "gitlab" in body
    assert "review_waiting_count" in body["gitlab"]
    assert "failed_pipeline_count" in body["gitlab"]

    assert "tests" in body
    assert "fail_count" in body["tests"]
    assert "pass_count" in body["tests"]

    assert "ai" in body
    assert "enabled" in body["ai"]
    assert "available" in body["ai"]
    assert "cached" in body["ai"]

    # No large/raw payloads leaking into the summary.
    assert "snippet" not in resp.text
    assert "raw_source" not in resp.text
    assert "raw_ics" not in resp.text


def test_dashboard_summary_requires_api_key():
    with _client() as c:
        resp = c.get("/api/dashboard/summary")
    assert resp.status_code == 401


def test_dashboard_summary_does_not_include_email_bodies(monkeypatch):
    """Insert a message with an obviously-identifiable snippet and
    confirm it never surfaces in the summary payload, even indirectly
    through action_required items."""
    db = SessionLocal()
    try:
        db.add(
            EmailMessage(
                message_id="<summary-test@example.com>",
                folder="INBOX",
                subject="Summary body leak test",
                from_addr="someone@example.com",
                to_addrs=settings.gmail_username or "me@example.com",
                unread=True,
                is_addressed_to_me=True,
                action_required=True,
                snippet="SECRET_BODY_CONTENT_MARKER",
            )
        )
        db.commit()
    finally:
        db.close()

    with _client() as c:
        resp = c.get("/api/dashboard/summary", headers=API_HEADERS)

    assert "SECRET_BODY_CONTENT_MARKER" not in resp.text

    db = SessionLocal()
    try:
        db.query(EmailMessage).filter(EmailMessage.message_id == "<summary-test@example.com>").delete()
        db.commit()
    finally:
        db.close()