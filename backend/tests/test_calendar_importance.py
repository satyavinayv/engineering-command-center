"""
Pure-logic tests for the calendar deterministic classification helpers.
These don't touch the DB or parse real ICS - they call the same
functions calendar_sync.py uses internally, with plain inputs.
"""
import sys
import types

# icalendar isn't installed in every environment these tests might run
# in (e.g. CI without the full requirements set); the functions we're
# testing here don't actually need it, so stub it out if missing rather
# than skip the whole module.
try:
    import icalendar  # noqa: F401
except ImportError:
    sys.modules["icalendar"] = types.SimpleNamespace(Calendar=object)

from app.config import settings
from app.services.calendar_sync import _classify_importance


def test_manager_as_organizer_is_high_priority(monkeypatch):
    monkeypatch.setattr(settings, "calendar_manager_email", "manager@company.com")
    importance, reason = _classify_importance("1:1 sync", "manager@company.com", ["me@company.com"])
    assert importance == "HIGH"
    assert "manager" in reason.lower()


def test_manager_as_attendee_is_high_priority(monkeypatch):
    monkeypatch.setattr(settings, "calendar_manager_email", "manager@company.com")
    importance, _ = _classify_importance(
        "Random sync", "someone@company.com", ["me@company.com", "manager@company.com"]
    )
    assert importance == "HIGH"


def test_keyword_match_is_high_priority(monkeypatch):
    monkeypatch.setattr(settings, "calendar_manager_email", "")
    importance, reason = _classify_importance("Sprint Planning", "pm@company.com", ["me@company.com"])
    assert importance == "HIGH"
    assert "keyword" in reason.lower()


def test_no_match_is_normal_priority(monkeypatch):
    monkeypatch.setattr(settings, "calendar_manager_email", "")
    importance, reason = _classify_importance("Random catchup", "colleague@company.com", ["me@company.com"])
    assert importance == "NORMAL"
    assert reason is None


def test_manager_match_takes_precedence_over_absence_of_keyword(monkeypatch):
    monkeypatch.setattr(settings, "calendar_manager_email", "manager@company.com")
    importance, reason = _classify_importance("Boring status update", "manager@company.com", [])
    assert importance == "HIGH"