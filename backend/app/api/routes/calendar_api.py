"""
Calendar API endpoints (Phase 4). Read-only against the DB except for
one deliberate write path -- uploading a fresh ICS export -- since
this integration has no live API to poll. See
app/integrations/calendar_integration.py for why.

Wire this in wherever backend/app/main.py includes the jira/gitlab
routers, e.g.:
    from app.api.calendar import router as calendar_router
    app.include_router(calendar_router)
(Adjust the import path if your routers live somewhere other than
app/api/ -- I haven't seen main.py so this mirrors the jira_integration
import conventions I have seen.)
"""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import require_api_key
from app.database import SessionLocal
from app.models import CalendarEvent

router = APIRouter(prefix="/api/calendar", tags=["calendar"], dependencies=[Depends(require_api_key)])

# A real Google Calendar export .ics is at most a few MB even with a
# couple years of history; 10MB is generous headroom while still
# rejecting anything absurd (spec: "add a reasonable maximum upload
# size").
MAX_ICS_UPLOAD_BYTES = 10 * 1024 * 1024


def _now_utc() -> datetime:
    """Naive UTC "now" — matches the storage convention used
    everywhere in this codebase (calendar_sync.py/gmail_sync.py strip
    tzinfo before storing, action_engine.py already uses
    datetime.utcnow()). Comparing that against datetime.now() (naive
    LOCAL time) was the actual bug here — off by your UTC offset,
    silently, depending on the server's timezone. Frontend still
    converts to local time for display; this only fixes internal
    comparisons."""
    return datetime.utcnow()


@router.post("/import")
async def import_ics(file: UploadFile = File(...)) -> dict:
    """Upload a freshly-exported .ics file. Google Calendar ->
    Settings -> Import & export -> Export gives you a .zip; unzip it
    and upload the .ics inside (usually named after your email
    address)."""
    if not file.filename or not file.filename.endswith(".ics"):
        raise HTTPException(400, "Expected a .ics file")

    raw = await file.read()
    if len(raw) > MAX_ICS_UPLOAD_BYTES:
        raise HTTPException(
            413, f"File too large ({len(raw)} bytes) - max is {MAX_ICS_UPLOAD_BYTES} bytes"
        )

    from app.integrations.calendar_integration import CalendarIntegration
    from app.services.calendar_sync import persist_ics_file

    integration = CalendarIntegration()
    integration.import_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize: take only the basename, so a crafted filename like
    # "../../../etc/somewhere.ics" can't write outside import_dir.
    # This does not change ICS parsing behavior at all - parsing
    # happens on `raw` bytes, independent of what we name the file.
    safe_name = Path(file.filename).name
    stamp = _now_utc().strftime("%Y%m%dT%H%M%S")
    (integration.import_dir / f"{stamp}-{safe_name}").write_bytes(raw)

    result = persist_ics_file(raw)
    return {"status": "imported", **result}


@router.get("/events")
def list_events(upcoming_only: bool = True) -> list[dict]:
    db = SessionLocal()
    try:
        query = select(CalendarEvent)
        if upcoming_only:
            query = query.where(CalendarEvent.start_at >= _now_utc())
        rows = db.execute(query.order_by(CalendarEvent.start_at.asc())).scalars().all()
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/created")
def created_by_me() -> list[dict]:
    """Meetings I created -- spec section 6A."""
    db = SessionLocal()
    try:
        rows = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.is_organizer.is_(True))
            .order_by(CalendarEvent.start_at.asc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/pending-response")
def pending_response() -> list[dict]:
    """Meetings I have NOT responded to -- spec section 6C, the
    'especially important' bucket."""
    db = SessionLocal()
    try:
        rows = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.is_organizer.is_(False),
                CalendarEvent.my_rsvp_status == "NEEDS-ACTION",
                CalendarEvent.start_at >= _now_utc(),
            )
            .order_by(CalendarEvent.start_at.asc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/accepted")
def accepted() -> list[dict]:
    """Meetings where I responded YES -- spec section 6B."""
    db = SessionLocal()
    try:
        rows = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.my_rsvp_status == "ACCEPTED")
            .order_by(CalendarEvent.start_at.asc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


def _serialize(row: CalendarEvent) -> dict:
    return {
        "source_uid": row.source_uid,
        "title": row.title,
        "start_at": row.start_at.isoformat() if row.start_at else None,
        "end_at": row.end_at.isoformat() if row.end_at else None,
        "all_day": row.all_day,
        "location": row.location,
        "organizer_email": row.organizer_email,
        "is_organizer": row.is_organizer,
        "my_rsvp_status": row.my_rsvp_status,
        "attendees": row.attendees.split(",") if row.attendees else [],
        "meeting_link": row.meeting_link,
        "calendar_link": row.calendar_link,
        "importance": row.importance,
        "importance_reason": row.importance_reason,
    }