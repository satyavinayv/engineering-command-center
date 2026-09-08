"""
Calendar integration — Google Workspace, ICS-import based.

We do NOT use the Google Calendar API or CalDAV here. Both require
OAuth 2.0 credentials from Google Cloud Console, and this account
can't create a new GCP project (org policy blocks it). There's also
no private "secret address in iCal format" URL available (hidden/
disabled by the Workspace admin), so there's no URL to poll either.

Instead: you periodically export your calendar from Google Calendar
(Settings -> Import & export -> Export) and either
  (a) drop the extracted .ics file into CALENDAR_ICS_IMPORT_DIR, or
  (b) upload it through POST /api/calendar/import
Either path lands here as a batch of events to parse and persist.

"Live sync" doesn't apply the way it does for Jira/GitLab -- there is
no polling cursor against an external API. `incremental_sync` means
"process any import files that appeared since the last run." Once
persisted, the dashboard reads from the DB exactly like every other
integration -- spec section 37's source-of-truth rule still holds;
the "source" is just a file you hand us instead of an API we poll.

No RSVP write-back is possible via this path (that needs the same
OAuth we're avoiding) -- see calendar_link in the DB model / API for
the "reliable link to the original event" fallback spec section 6D
calls for instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings
from app.integrations.base import (
    Integration,
    IntegrationAuthError,
    IntegrationConnectionError,
    SyncResult,
)


class CalendarIntegration(Integration):
    key = "calendar"
    display_name = "Calendar (Google, ICS import)"

    def __init__(self) -> None:
        self.import_dir = Path(settings.calendar_ics_import_dir)

    def is_configured(self) -> bool:
        # Both matter: the import directory is where files land, but
        # without calendar_primary_email, RSVP status and "is this
        # mine?" detection silently produce wrong answers (everything
        # looks like NEEDS-ACTION / not-organizer) rather than failing
        # loudly - so we treat it as required, not optional.
        return bool(settings.calendar_ics_import_dir) and bool(settings.calendar_primary_email)

    def authenticate(self) -> None:
        # Nothing to authenticate against -- this is a file-drop
        # integration. We just make sure the import directory exists
        # and is writable, since /api/calendar/import writes into it.
        if not self.is_configured():
            raise IntegrationAuthError(
                "CALENDAR_ICS_IMPORT_DIR and/or CALENDAR_PRIMARY_EMAIL is not set"
            )
        try:
            self.import_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise IntegrationConnectionError(
                f"Cannot access calendar import directory: {exc}"
            ) from exc

    def test_connection(self) -> bool:
        try:
            self.authenticate()
            return True
        except (IntegrationAuthError, IntegrationConnectionError):
            return False

    def _unprocessed_files(self, cursor: str | None) -> list[Path]:
        cursor_mtime = float(cursor) if cursor else 0.0
        return sorted(
            p for p in self.import_dir.glob("*.ics") if p.stat().st_mtime > cursor_mtime
        )

    def _sync_files(self, files: list[Path]) -> SyncResult:
        from app.services.calendar_sync import persist_ics_file

        total_fetched = 0
        new_count = 0
        updated_count = 0
        latest_mtime = 0.0

        for path in files:
            raw = path.read_bytes()
            result = persist_ics_file(raw)
            total_fetched += result["fetched"]
            new_count += result["new"]
            updated_count += result["updated"]
            latest_mtime = max(latest_mtime, path.stat().st_mtime)

        return SyncResult(
            records_fetched=total_fetched,
            records_new=new_count,
            records_updated=updated_count,
            cursor=str(latest_mtime) if latest_mtime else None,
        )

    def fetch_initial_data(self, window_days: int | None = None) -> SyncResult:
        self.authenticate()
        return self._sync_files(self._unprocessed_files(cursor=None))

    def incremental_sync(self, cursor: str | None) -> SyncResult:
        self.authenticate()
        files = self._unprocessed_files(cursor)
        if not files:
            return SyncResult(records_fetched=0, records_new=0, records_updated=0, cursor=cursor)
        return self._sync_files(files)

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        from app.database import SessionLocal
        from app.models import CalendarEvent

        db = SessionLocal()
        try:
            row = db.query(CalendarEvent).filter(CalendarEvent.source_uid == item_id).first()
            if not row:
                return None
            return {
                "source_uid": row.source_uid,
                "title": row.title,
                "start_at": row.start_at.isoformat() if row.start_at else None,
                "end_at": row.end_at.isoformat() if row.end_at else None,
                "organizer_email": row.organizer_email,
                "is_organizer": row.is_organizer,
                "my_rsvp_status": row.my_rsvp_status,
                "attendees": row.attendees,
                "meeting_link": row.meeting_link,
                "calendar_link": row.calendar_link,
                "importance": row.importance,
                "importance_reason": row.importance_reason,
            }
        finally:
            db.close()

    def search(self, query: str) -> list[dict[str, Any]]:
        """Deterministic search over already-imported events (spec section 25)."""
        from app.database import SessionLocal
        from app.models import CalendarEvent

        db = SessionLocal()
        try:
            like = f"%{query}%"
            rows = (
                db.query(CalendarEvent)
                .filter((CalendarEvent.title.ilike(like)) | (CalendarEvent.location.ilike(like)))
                .order_by(CalendarEvent.start_at.desc())
                .limit(25)
                .all()
            )
            return [
                {
                    "source_uid": r.source_uid,
                    "title": r.title,
                    "start_at": r.start_at.isoformat() if r.start_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()