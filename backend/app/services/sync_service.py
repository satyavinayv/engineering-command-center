"""
Generic synchronization runner.

This module is the single place that decides whether an integration
performs an initial backfill or an incremental sync.

The integration itself only implements:

    fetch_initial_data(...)
    incremental_sync(...)

The runner persists the sync outcome in sync_status so the health
page always has an accurate view of the integration.

Flow:

    First sync
        -> fetch_initial_data()

    Subsequent sync
        -> incremental_sync(cursor)

Every sync records:

    - connected
    - last_sync_at
    - last_error
    - records_synced
    - cursor
"""

import logging
from datetime import datetime, timezone

from app.database import SessionLocal
from app.integrations.base import Integration, IntegrationError
from app.models import SyncStatus


logger = logging.getLogger(__name__)

DEFAULT_BACKFILL_WINDOW_DAYS = 30


def run_sync(
    integration: Integration,
    backfill_window_days: int = DEFAULT_BACKFILL_WINDOW_DAYS,
) -> dict:
    """
    Run one synchronization for an integration.

    If a persisted cursor exists, incremental_sync() is used.

    If no cursor exists, fetch_initial_data() is used.

    Returns a small result dictionary for logging and diagnostics.
    """

    db = SessionLocal()

    started_at = datetime.now(timezone.utc)

    try:
        status = (
            db.query(SyncStatus)
            .filter_by(
                integration_key=integration.key
            )
            .one_or_none()
        )

        sync_type = (
            "incremental"
            if status and status.cursor
            else "initial"
        )

        logger.info(
            "[SYNC] Starting %s sync for '%s'",
            sync_type,
            integration.key,
        )

        try:
            # --------------------------------------------------------
            # Initial backfill
            # --------------------------------------------------------
            if sync_type == "initial":
                logger.info(
                    "[SYNC] '%s' has no persisted cursor; "
                    "running initial backfill (%s days)",
                    integration.key,
                    backfill_window_days,
                )

                result = integration.fetch_initial_data(
                    window_days=backfill_window_days
                )

            # --------------------------------------------------------
            # Incremental sync
            # --------------------------------------------------------
            else:
                logger.info(
                    "[SYNC] '%s' using persisted cursor: %s",
                    integration.key,
                    status.cursor,
                )

                result = integration.incremental_sync(
                    cursor=status.cursor
                )

            # --------------------------------------------------------
            # Create sync status if this is the first run.
            # --------------------------------------------------------
            if status is None:
                status = SyncStatus(
                    integration_key=integration.key
                )
                db.add(status)

            # --------------------------------------------------------
            # Record successful sync.
            # --------------------------------------------------------
            status.connected = True
            status.last_sync_at = datetime.now(timezone.utc)
            status.last_error = None

            records_fetched = getattr(
                result,
                "records_fetched",
                0,
            )

            status.records_synced = (
                (status.records_synced or 0)
                + records_fetched
            )

            if result.cursor is not None:
                status.cursor = result.cursor

            db.commit()

            elapsed = (
                datetime.now(timezone.utc)
                - started_at
            ).total_seconds()

            logger.info(
                "[SYNC] Completed %s sync for '%s' "
                "| records=%s | cursor=%s | %.2fs",
                sync_type,
                integration.key,
                records_fetched,
                result.cursor,
                elapsed,
            )

            return {
                "integration": integration.key,
                "sync_type": sync_type,
                "records_fetched": records_fetched,
                "cursor": result.cursor,
                "success": True,
            }

        except IntegrationError as exc:
            # --------------------------------------------------------
            # Expected integration failure.
            # --------------------------------------------------------
            if status is None:
                status = SyncStatus(
                    integration_key=integration.key
                )
                db.add(status)

            status.connected = False
            status.last_error = str(exc)

            db.commit()

            logger.error(
                "[SYNC] Integration error for '%s': %s",
                integration.key,
                exc,
            )

            return {
                "integration": integration.key,
                "sync_type": sync_type,
                "records_fetched": 0,
                "cursor": (
                    status.cursor
                    if status
                    else None
                ),
                "success": False,
                "error": str(exc),
            }

        except Exception as exc:
            # --------------------------------------------------------
            # Unexpected failure.
            #
            # Important: record it in sync_status as well.
            # --------------------------------------------------------
            db.rollback()

            status = (
                db.query(SyncStatus)
                .filter_by(
                    integration_key=integration.key
                )
                .one_or_none()
            )

            if status is None:
                status = SyncStatus(
                    integration_key=integration.key
                )
                db.add(status)

            status.connected = False
            status.last_error = (
                f"{type(exc).__name__}: {exc}"
            )

            db.commit()

            logger.exception(
                "[SYNC] Unexpected sync failure for '%s'",
                integration.key,
            )

            return {
                "integration": integration.key,
                "sync_type": sync_type,
                "records_fetched": 0,
                "cursor": (
                    status.cursor
                    if status
                    else None
                ),
                "success": False,
                "error": str(exc),
            }

    finally:
        db.close()