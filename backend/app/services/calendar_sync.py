"""
Deterministic ICS parsing + persistence for the Calendar integration
(Phase 4). No AI involved anywhere in this file -- see spec sections
6 and 37. Requires the `icalendar` package (add to requirements.txt).
"""

from __future__ import annotations

import base64
import re
from datetime import date, datetime, timezone

from icalendar import Calendar

from app.config import settings
from app.database import SessionLocal
from app.models import CalendarEvent

MEETING_LINK_PATTERN = re.compile(
    r"https?://[^\s\"<>]*(zoom\.us|meet\.google\.com|teams\.microsoft\.com)[^\s\"<>]*",
    re.IGNORECASE,
)


def _as_datetime(field) -> datetime | None:
    if field is None:
        return None
    value = field.dt
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    return None


def _is_all_day(field) -> bool:
    if field is None:
        return False
    value = field.dt
    return isinstance(value, date) and not isinstance(value, datetime)


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _my_partstat(component, my_email: str) -> str:
    if not my_email:
        return "NEEDS-ACTION"
    for att in _as_list(component.get("attendee")):
        addr = str(att).replace("mailto:", "").strip().lower()
        if addr == my_email.lower():
            return str(att.params.get("PARTSTAT", "NEEDS-ACTION")).upper()
    return "NEEDS-ACTION"


def _attendee_emails(component) -> list[str]:
    return [str(a).replace("mailto:", "").strip() for a in _as_list(component.get("attendee"))]


def _organizer_email(component) -> str | None:
    organizer = component.get("organizer")
    return str(organizer).replace("mailto:", "").strip() if organizer else None


def _meeting_link(component) -> str | None:
    for field in ("location", "description", "url"):
        val = component.get(field)
        if not val:
            continue
        match = MEETING_LINK_PATTERN.search(str(val))
        if match:
            return match.group(0)
    return None


def _google_calendar_link(uid: str) -> str | None:
    """Best-effort deep link to open the event in Google Calendar's
    web UI. Google's `eid` param is base64(uid + " " + calendar_id);
    this assumes your primary calendar id. Treat as "usually works,
    not guaranteed" -- if it 404s, the raw UID is still stored on the
    event for manual lookup, per spec section 6D's fallback."""
    if not settings.calendar_primary_email:
        return None
    raw = f"{uid} {settings.calendar_primary_email}".encode()
    eid = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"https://calendar.google.com/calendar/event?eid={eid}"


def _classify_importance(
    title: str, organizer_email: str | None, attendees: list[str]
) -> tuple[str, str | None]:
    """Deterministic importance rules -- spec section 6D. Configurable
    via CALENDAR_MANAGER_EMAIL / CALENDAR_IMPORTANT_KEYWORDS. AI
    classification (Phase 7) layers on top of this later; it never
    replaces it."""
    title_lower = title.lower()
    attendees_lower = [a.lower() for a in attendees]

    if settings.calendar_manager_email:
        mgr = settings.calendar_manager_email.lower()
        if organizer_email and organizer_email.lower() == mgr:
            return "HIGH", "Organized by manager"
        if mgr in attendees_lower:
            return "HIGH", "Manager is an attendee"

    for keyword in settings.calendar_important_keywords_list:
        if keyword.lower() in title_lower:
            return "HIGH", f"Title matches keyword: {keyword}"

    return "NORMAL", None


def persist_ics_file(raw: bytes) -> dict:
    cal = Calendar.from_ical(raw)
    db = SessionLocal()
    new_count = 0
    updated_count = 0
    fetched = 0

    # Tracks events we've already encountered during THIS import.
    # This is necessary because SQLAlchemy may not have flushed a newly
    # added object to SQLite when the same UID appears again in the ICS.
    seen: dict[str, CalendarEvent] = {}

    try:
        for component in cal.walk("VEVENT"):
            uid = str(component.get("uid") or "")
            if not uid:
                continue

            fetched += 1

            title = str(component.get("summary", ""))
            dtstart = component.get("dtstart")
            start_at = _as_datetime(dtstart)
            end_at = _as_datetime(component.get("dtend"))
            all_day = _is_all_day(dtstart)
            location = str(component.get("location", ""))
            organizer_email = _organizer_email(component)
            attendees = _attendee_emails(component)
            my_rsvp = _my_partstat(component, settings.calendar_primary_email)

            is_organizer = bool(
                organizer_email
                and settings.calendar_primary_email
                and organizer_email.lower()
                == settings.calendar_primary_email.lower()
            )

            meeting_link = _meeting_link(component)
            calendar_link = _google_calendar_link(uid)
            importance, importance_reason = _classify_importance(
                title, organizer_email, attendees
            )
            raw_ics = component.to_ical().decode(
                "utf-8", errors="replace"
            )

            # First check objects encountered earlier in THIS ICS file.
            existing = seen.get(uid)

            # If this UID wasn't seen in this import, check the database.
            if existing is None:
                existing = (
                    db.query(CalendarEvent)
                    .filter(CalendarEvent.source_uid == uid)
                    .first()
                )

            if existing:
                existing.title = title
                existing.start_at = start_at
                existing.end_at = end_at
                existing.all_day = all_day
                existing.location = location
                existing.organizer_email = organizer_email
                existing.is_organizer = is_organizer
                existing.my_rsvp_status = my_rsvp
                existing.attendees = ",".join(attendees)
                existing.meeting_link = meeting_link
                existing.calendar_link = calendar_link
                existing.importance = importance
                existing.importance_reason = importance_reason
                existing.raw_ics = raw_ics

                # Remember it in case the same UID appears again.
                seen[uid] = existing

                updated_count += 1

            else:
                existing = CalendarEvent(
                    source_uid=uid,
                    title=title,
                    start_at=start_at,
                    end_at=end_at,
                    all_day=all_day,
                    location=location,
                    organizer_email=organizer_email,
                    is_organizer=is_organizer,
                    my_rsvp_status=my_rsvp,
                    attendees=",".join(attendees),
                    meeting_link=meeting_link,
                    calendar_link=calendar_link,
                    importance=importance,
                    importance_reason=importance_reason,
                    raw_ics=raw_ics,
                )

                db.add(existing)

                # Important: keep the pending object in memory so a
                # duplicate UID later in the same ICS doesn't result
                # in another INSERT.
                seen[uid] = existing

                new_count += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return {
        "fetched": fetched,
        "new": new_count,
        "updated": updated_count,
    }

