"""
Background synchronization scheduler.

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
    Execute exactly one synchronization job.

    Each integration is isolated. A failure in one integration does not
    stop the scheduler or affect other integrations.
    """

    logger.info(
        "============================================================"
    )
    logger.info(
        "[SCHEDULER] Triggered integration='%s'",
        integration_key,
    )

    # ------------------------------------------------------------
    # Look up integration.
    # ------------------------------------------------------------
    integration = registry.get(integration_key)

    if integration is None:
        logger.error(
            "[SCHEDULER] Integration '%s' is NOT registered",
            integration_key,
        )
        return

    # ------------------------------------------------------------
    # Configuration diagnostics.
    # ------------------------------------------------------------
    configured = integration.is_configured()

    logger.info(
        "[SCHEDULER] integration='%s' class='%s' configured=%s",
        integration_key,
        integration.__class__.__name__,
        configured,
    )

    # Do not log secrets/tokens/passwords.
    if integration_key == "jira":
        logger.info(
            "[SCHEDULER] Jira base_url=%r",
            getattr(integration, "base_url", None),
        )

    elif integration_key == "gitlab":
        logger.info(
            "[SCHEDULER] GitLab base_url=%r projects=%r",
            getattr(integration, "base_url", None),
            getattr(integration, "project_ids", None),
        )

    elif integration_key == "opensearch":
        logger.info(
            "[SCHEDULER] OpenSearch host=%r",
            getattr(integration, "host", None),
        )

    elif integration_key == "calendar":
        logger.info(
            "[SCHEDULER] Calendar provider=%r",
            getattr(integration, "provider", None),
        )

    elif integration_key == "gmail":
        logger.info(
            "[SCHEDULER] Gmail configured=%s",
            configured,
        )

    # ------------------------------------------------------------
    # If not configured, let run_sync record the failure.
    #
    # We intentionally do NOT return here.
    # ------------------------------------------------------------
    if not configured:
        logger.warning(
            "[SCHEDULER] Integration '%s' is not configured",
            integration_key,
        )

    # ------------------------------------------------------------
    # Gmail lock.
    # ------------------------------------------------------------
    lock = (
        _gmail_sync_lock
        if integration_key == "gmail"
        else None
    )

    if lock is not None:
        acquired = lock.acquire(blocking=False)

        if not acquired:
            logger.warning(
                "[SCHEDULER] Gmail sync is already running; "
                "skipping overlapping execution"
            )
            return

    else:
        acquired = False

    try:
        # --------------------------------------------------------
        # Run sync.
        # --------------------------------------------------------
        result = run_sync(integration)

        # --------------------------------------------------------
        # IMPORTANT:
        # run_sync returns success=False for integration failures.
        # Do not call those successful.
        # --------------------------------------------------------
        if result.get("success"):
            logger.info(
                "[SCHEDULER] SUCCESS integration='%s' "
                "type=%s records=%s cursor=%r",
                integration_key,
                result.get("sync_type"),
                result.get("records_fetched"),
                result.get("cursor"),
            )
        else:
            logger.error(
                "[SCHEDULER] FAILED integration='%s' "
                "type=%s error=%s",
                integration_key,
                result.get("sync_type"),
                result.get("error"),
            )

    except Exception:
        # This should normally not happen because run_sync catches
        # integration/runtime exceptions itself, but keep this guard
        # so one scheduler job can never kill the scheduler.
        logger.exception(
            "[SCHEDULER] Unexpected scheduler failure "
            "for integration='%s'",
            integration_key,
        )

    finally:
        if lock is not None and acquired:
            lock.release()

    logger.info(
        "[SCHEDULER] Finished integration='%s'",
        integration_key,
    )
    logger.info(
        "============================================================"
    )


def _ai_summary_job() -> None:
    """
    Pre-generate the daily AI briefing when AI is enabled.
    """

    if not settings.ai_enabled:
        logger.debug(
            "[AI] AI disabled; skipping summary generation"
        )
        return

    try:
        from app.services.ai_summary import (
            get_or_generate_daily_briefing,
        )

        logger.info(
            "[AI] Running scheduled daily briefing generation"
        )

        get_or_generate_daily_briefing(
            force=False
        )

    except Exception:
        logger.exception(
            "[AI] Summary pre-generation failed"
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

    # ------------------------------------------------------------
    # Validate intervals.
    # ------------------------------------------------------------
    for integration_key, minutes in intervals.items():
        if minutes <= 0:
            raise ValueError(
                f"Invalid sync interval for "
                f"'{integration_key}': {minutes}. "
                f"Interval must be greater than zero."
            )

    # ------------------------------------------------------------
    # Register integration jobs.
    # ------------------------------------------------------------
    for integration_key, minutes in intervals.items():
        print(
            f"Registering job: {integration_key} "
            f"every {minutes} minute(s)",
            flush=True,
        )

        scheduler.add_job(
            _sync_job,
            trigger="interval",
            minutes=minutes,
            args=[integration_key],
            id=f"sync_{integration_key}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,

            # Run immediately when scheduler starts.
            next_run_time=datetime.now(),
        )

    # ------------------------------------------------------------
    # Register AI summary job.
    #
    # Do NOT run this immediately. The first briefing can be
    # generated on its normal configured interval.
    # ------------------------------------------------------------
    scheduler.add_job(
        _ai_summary_job,
        trigger="interval",
        minutes=settings.ai_summary_interval_minutes,
        id="ai_summary",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # ------------------------------------------------------------
    # Start scheduler.
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # Print registered jobs.
    # ------------------------------------------------------------
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
    """
    Stop the scheduler gracefully.
    """

    if scheduler.running:
        logger.info(
            "Stopping background sync scheduler"
        )

        scheduler.shutdown(
            wait=False
        )

        logger.info(
            "Background sync scheduler stopped"
        )