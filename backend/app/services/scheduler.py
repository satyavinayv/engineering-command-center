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


def start_scheduler() -> None:
    intervals = {
        "jira": settings.sync_interval_jira,
        "gitlab": settings.sync_interval_gitlab,
        "opensearch": settings.sync_interval_opensearch,
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


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
