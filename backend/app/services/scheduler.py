"""
Background sync scheduling (spec section 19). Each configured
integration syncs on its own interval, independently — one integration
being slow or broken never blocks another (see error handling in
sync_service.run_sync, which always records a per-integration outcome).

GitLab is polling here too for Phase 2; adding a webhook receiver
(spec section 19's preferred approach for GitLab) is a fast-follow once
polling is verified working end-to-end.

Note: OpenSearch sync depends on Jira issues already being in the DB
(it only looks up executions for test-case keys it already knows about
from jira_issues). If Jira hasn't synced yet, OpenSearch sync simply
finds zero test cases and does nothing that interval — it self-corrects
once Jira catches up, no explicit ordering needed between the two jobs.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.integrations.registry import registry
from app.services.sync_service import run_sync

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _sync_job(integration_key: str) -> None:
    integration = registry.get(integration_key)
    if not integration or not integration.is_configured():
        return
    try:
        run_sync(integration)
    except Exception:  # noqa: BLE001 - a scheduled job must never crash the app
        logger.exception("Background sync failed for integration '%s'", integration_key)


def _ai_summary_job() -> None:
    """Pre-generates the daily briefing so the dashboard always reads a
    cached, instant result (spec section 18) instead of triggering a
    live AI call on page load. No-ops cleanly if AI is disabled."""
    if not settings.ai_enabled:
        return
    try:
        from app.services.ai_summary import get_or_generate_daily_briefing

        get_or_generate_daily_briefing(force=False)
    except Exception:  # noqa: BLE001
        logger.exception("AI summary pre-generation failed")


def start_scheduler() -> None:
    intervals = {
        "jira": settings.sync_interval_jira,
        "gitlab": settings.sync_interval_gitlab,
        "opensearch": settings.sync_interval_opensearch,
        "calendar": settings.sync_interval_calendar,
        "gmail": settings.sync_interval_gmail,
    }
    for key, minutes in intervals.items():
        scheduler.add_job(
            _sync_job,
            "interval",
            minutes=minutes,
            args=[key],
            id=f"sync_{key}",
            replace_existing=True,
        )
    if not scheduler.running:
        scheduler.start()

    scheduler.add_job(
        _ai_summary_job,
        "interval",
        minutes=settings.ai_summary_interval_minutes,
        id="ai_summary",
        replace_existing=True,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)