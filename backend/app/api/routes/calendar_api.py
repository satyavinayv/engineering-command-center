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

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import require_api_key
from app.database import SessionLocal
from app.models import CalendarEvent

router = APIRouter(prefix="/api/calendar", tags=["calendar"], dependencies=[Depends(require_api_key)])


@router.post("/import")
async def import_ics(file: UploadFile = File(...)) -> dict:
    """Upload a freshly-exported .ics file. Google Calendar ->
    Settings -> Import & export -> Export gives you a .zip; unzip it
    and upload the .ics inside (usually named after your email
    address)."""
    if not file.filename or not file.filename.endswith(".ics"):
        raise HTTPException(400, "Expected a .ics file")

    raw = await file.read()

    from app.integrations.calendar_integration import CalendarIntegration
    from app.services.calendar_sync import persist_ics_file

    integration = CalendarIntegration()
    integration.import_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    (integration.import_dir / f"{stamp}-{file.filename}").write_bytes(raw)

    result = persist_ics_file(raw)
    return {"status": "imported", **result}


@router.get("/events")
def list_events(upcoming_only: bool = True) -> list[dict]:
    db = SessionLocal()
    try:
        query = select(CalendarEvent)
        if upcoming_only:
            query = query.where(CalendarEvent.start_at >= datetime.now())
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
                CalendarEvent.start_at >= datetime.now(),
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