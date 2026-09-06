"""
Generic sync runner. Works for any Integration: does an initial backfill
the first time, incremental sync (using the persisted cursor) every time
after, and always records the outcome in sync_status — success or
failure — so the health page (spec section 29) is always accurate. This
is the ONE place that decides "backfill vs incremental"; integrations
themselves don't need to know which one is happening.
"""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.integrations.base import Integration, IntegrationError
from app.models import SyncStatus

DEFAULT_BACKFILL_WINDOW_DAYS = 30


def run_sync(integration: Integration, backfill_window_days: int = DEFAULT_BACKFILL_WINDOW_DAYS) -> None:
    db = SessionLocal()
    try:
        status = db.query(SyncStatus).filter_by(integration_key=integration.key).one_or_none()
        try:
            if status and status.cursor:
                result = integration.incremental_sync(cursor=status.cursor)
            else:
                result = integration.fetch_initial_data(window_days=backfill_window_days)

            if not status:
                status = SyncStatus(integration_key=integration.key)
                db.add(status)

            status.connected = True
            status.last_sync_at = datetime.now(timezone.utc)
            status.last_error = None
            status.records_synced = (status.records_synced or 0) + result.records_fetched
            if result.cursor:
                status.cursor = result.cursor

        except IntegrationError as exc:
            if not status:
                status = SyncStatus(integration_key=integration.key)
                db.add(status)
            status.connected = False
            status.last_error = str(exc)

        db.commit()
    finally:
        db.close()
