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
from typing import Any

from app.database import SessionLocal
from app.integrations.base import Integration, IntegrationError
from app.models import SyncStatus

logger = logging.getLogger(__name__)

DEFAULT_BACKFILL_WINDOW_DAYS = 30


def run_sync(
        integration: Integration,
        backfill_window_days: int = DEFAULT_BACKFILL_WINDOW_DAYS,
) -> dict[str, Any]:
    """
    Run exactly one synchronization for an integration.

    The runner decides whether this is an initial or incremental sync.

    Initial:
        No persisted cursor exists.

    Incremental:
        A persisted cursor exists.

    The integration is responsible only for fetching and persisting its
    own domain data. This function is responsible for sync_status.

    Returns:
        {
            "integration": str,
            "sync_type": "initial" | "incremental",
            "records_fetched": int,
            "cursor": str | None,
            "success": bool,
            "error": str | None,
        }
    """

    integration_key = integration.key
    started_at = datetime.now(timezone.utc)

    db = SessionLocal()

    try:
        # ------------------------------------------------------------
        # Load existing sync status.
        # ------------------------------------------------------------
        status = (
            db.query(SyncStatus)
            .filter_by(integration_key=integration_key)
            .one_or_none()
        )

        # ------------------------------------------------------------
        # Decide initial vs incremental.
        # ------------------------------------------------------------
        if status is not None and status.cursor:
            sync_type = "incremental"
        else:
            sync_type = "initial"

        logger.info(
            "[SYNC] Starting %s sync for '%s'",
            sync_type,
            integration_key,
        )

        # ------------------------------------------------------------
        # Execute integration sync.
        # ------------------------------------------------------------
        try:
            if sync_type == "initial":
                logger.info(
                    "[SYNC] '%s' has no cursor; "
                    "running initial backfill (%s days)",
                    integration_key,
                    backfill_window_days,
                )

                result = integration.fetch_initial_data(
                    window_days=backfill_window_days
                )

            else:
                logger.info(
                    "[SYNC] '%s' using cursor=%r",
                    integration_key,
                    status.cursor,
                )

                result = integration.incremental_sync(
                    cursor=status.cursor
                )

            # --------------------------------------------------------
            # Validate result.
            # --------------------------------------------------------
            if result is None:
                raise IntegrationError(
                    f"Integration '{integration_key}' returned no SyncResult"
                )

            records_fetched = int(
                getattr(result, "records_fetched", 0) or 0
            )

            result_cursor = getattr(
                result,
                "cursor",
                None,
            )

            # --------------------------------------------------------
            # Create status row if this is the first successful sync.
            # --------------------------------------------------------
            if status is None:
                status = SyncStatus(
                    integration_key=integration_key
                )
                db.add(status)

            # --------------------------------------------------------
            # Record success.
            # --------------------------------------------------------
            status.connected = True
            status.last_sync_at = datetime.now(timezone.utc)
            status.last_error = None

            status.records_synced = (
                    (status.records_synced or 0)
                    + records_fetched
            )

            # Only replace the cursor when the integration returned one.
            if result_cursor is not None:
                status.cursor = result_cursor

            db.commit()

            elapsed = (
                    datetime.now(timezone.utc) - started_at
            ).total_seconds()

            logger.info(
                "[SYNC] SUCCESS integration='%s' "
                "type=%s records=%d cursor=%r elapsed=%.2fs",
                integration_key,
                sync_type,
                records_fetched,
                result_cursor,
                elapsed,
            )

            return {
                "integration": integration_key,
                "sync_type": sync_type,
                "records_fetched": records_fetched,
                "cursor": result_cursor,
                "success": True,
                "error": None,
            }

        # ------------------------------------------------------------
        # Expected integration failure.
        # ------------------------------------------------------------
        except IntegrationError as exc:
            db.rollback()

            # Reload status after rollback so the session is clean.
            status = (
                db.query(SyncStatus)
                .filter_by(integration_key=integration_key)
                .one_or_none()
            )

            if status is None:
                status = SyncStatus(
                    integration_key=integration_key
                )
                db.add(status)

            status.connected = False
            status.last_error = str(exc)

            db.commit()

            elapsed = (
                    datetime.now(timezone.utc) - started_at
            ).total_seconds()

            logger.error(
                "[SYNC] FAILED integration='%s' "
                "type=%s error=%s elapsed=%.2fs",
                integration_key,
                sync_type,
                exc,
                elapsed,
            )

            return {
                "integration": integration_key,
                "sync_type": sync_type,
                "records_fetched": 0,
                "cursor": (
                    status.cursor
                    if status is not None
                    else None
                ),
                "success": False,
                "error": str(exc),
            }

        # ------------------------------------------------------------
        # Unexpected programming/runtime failure.
        # ------------------------------------------------------------
        except Exception as exc:
            db.rollback()

            status = (
                db.query(SyncStatus)
                .filter_by(integration_key=integration_key)
                .one_or_none()
            )

            if status is None:
                status = SyncStatus(
                    integration_key=integration_key
                )
                db.add(status)

            status.connected = False
            status.last_error = (
                f"{type(exc).__name__}: {exc}"
            )

            db.commit()

            elapsed = (
                    datetime.now(timezone.utc) - started_at
            ).total_seconds()

            logger.exception(
                "[SYNC] UNEXPECTED FAILURE integration='%s' "
                "type=%s elapsed=%.2fs",
                integration_key,
                sync_type,
                elapsed,
            )

            return {
                "integration": integration_key,
                "sync_type": sync_type,
                "records_fetched": 0,
                "cursor": (
                    status.cursor
                    if status is not None
                    else None
                ),
                "success": False,
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }

    finally:
        db.close()
