"""
Background sync scheduling.

Each configured integration runs independently on its own interval.

All integration syncs run immediately when the scheduler starts and
then continue according to their configured intervals.

Gmail has an additional process-level lock because Gmail messages can
be fetched from multiple labels/folders and Gmail sync must not overlap.
"""

import logging
from datetime import datetime
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.integrations.registry import registry
from app.services.sync_service import run_sync

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# Prevent overlapping Gmail sync operations.
_gmail_sync_lock = Lock()


def _sync_job(integration_key: str) -> None:
    """
    Execute one integration sync.

    Each integration is isolated. A failure in one integration does not
    stop the scheduler or affect the other integrations.
    """

    logger.info(
        "Scheduled sync triggered for integration '%s'",
        integration_key,
    )

    integration = registry.get(integration_key)

    if integration is None:
        logger.warning(
            "Integration '%s' was NOT FOUND in the registry",
            integration_key,
        )
        return

    try:
        configured = integration.is_configured()
    except Exception:
        logger.exception(
            "Could not determine configuration for integration '%s'",
            integration_key,
        )
        return

    if not configured:
        logger.warning(
            "Integration '%s' is registered but NOT CONFIGURED; "
            "skipping sync",
            integration_key,
        )
        return

    lock = None

    if integration_key == "gmail":
        lock = _gmail_sync_lock

        if not lock.acquire(blocking=False):
            logger.warning(
                "Gmail sync is already running; "
                "skipping overlapping run"
            )
            return

    try:
        logger.info(
            "Starting scheduled sync for integration '%s'",
            integration_key,
        )

        result = run_sync(integration)

        logger.info(
            "Scheduled sync completed for integration '%s': %s",
            integration_key,
            result,
        )

    except Exception:
        logger.exception(
            "Background sync failed for integration '%s'",
            integration_key,
        )

    finally:
        if lock is not None:
            lock.release()


def _ai_summary_job() -> None:
    """
    Pre-generate the daily AI briefing when AI is enabled.
    """

    if not settings.ai_enabled:
        return

    try:
        from app.services.ai_summary import (
            get_or_generate_daily_briefing,
        )

        get_or_generate_daily_briefing(force=False)

    except Exception:
        logger.exception(
            "AI summary pre-generation failed"
        )


def start_scheduler() -> None:
    """
    Register and start all background sync jobs.

    Every integration runs immediately when the application starts,
    then repeats according to its configured interval.
    """

    print(
        "\n========== START_SCHEDULER CALLED ==========",
        flush=True,
    )

    intervals = {
        "jira": settings.sync_interval_jira,
        "gitlab": settings.sync_interval_gitlab,
        "opensearch": settings.sync_interval_opensearch,
        "calendar": settings.sync_interval_calendar,
        "gmail": settings.sync_interval_gmail,
    }

    print(
        f"Configured sync intervals: {intervals}",
        flush=True,
    )

    for integration_key, minutes in intervals.items():
        print(
            f"Registering job: {integration_key} "
            f"every {minutes} minute(s)",
            flush=True,
        )

        scheduler.add_job(
            _sync_job,
            "interval",
            minutes=minutes,
            args=[integration_key],
            id=f"sync_{integration_key}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(),
        )

    scheduler.add_job(
        _ai_summary_job,
        "interval",
        minutes=settings.ai_summary_interval_minutes,
        id="ai_summary",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    if not scheduler.running:
        scheduler.start()

        print(
            "========== SCHEDULER STARTED ==========",
            flush=True,
        )
    else:
        print(
            "========== SCHEDULER ALREADY RUNNING ==========",
            flush=True,
        )

    jobs = scheduler.get_jobs()

    print(
        f"========== REGISTERED JOBS: {len(jobs)} ==========",
        flush=True,
    )

    for job in jobs:
        print(
            f"JOB: id={job.id}, "
            f"next_run={job.next_run_time}",
            flush=True,
        )

    print(
        "========== START_SCHEDULER COMPLETE ==========\n",
        flush=True,
    )


def stop_scheduler() -> None:
    """Scheduled sync completed
    Stop the scheduler gracefully.
    """

    if scheduler.running:
        logger.info(
            "Stopping background sync scheduler"
        )

        scheduler.shutdown(wait=False)

        logger.info(
            "Background sync scheduler stopped"
        )
