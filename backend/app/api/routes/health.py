"""
Deterministic health endpoint (spec section 29 - System Health page).

Reads exclusively from the sync_status table - it does NOT call out to
Jira/GitLab/etc. live. Health always reflects the last completed
background sync, never a fresh network round-trip on every dashboard
load (spec section 36: dashboard load must never depend on sequential
external API calls). For an on-demand live check (e.g. an admin "Test
Connection" button), see POST /config/test-connection/{key}.

Left unauthenticated (unlike other routes) since it's low-sensitivity
status info and the frontend dashboard shell needs it before any other
call.
"""
from fastapi import APIRouter

from app.database import SessionLocal
from app.integrations.registry import registry
from app.models import SyncStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health():
    db = SessionLocal()
    try:
        status_by_key = {s.integration_key: s for s in db.query(SyncStatus).all()}
        integrations = []
        overall_ok = True

        for integration in registry.all():
            configured = integration.is_configured()

            # The mock integration is Phase 1's in-memory test double for
            # the framework itself - it never goes through the
            # background scheduler (there's nothing real to sync), so
            # it has no sync_status row. Report it as always healthy
            # rather than folding it into the DB-driven logic below.
            if integration.key == "mock":
                integrations.append(
                    {
                        "key": integration.key,
                        "display_name": integration.display_name,
                        "configured": True,
                        "connected": True,
                        "last_sync_at": None,
                        "last_error": None,
                        "records_synced": 0,
                    }
                )
                continue

            status = status_by_key.get(integration.key)
            connected = bool(status.connected) if status else False

            # Only a CONFIGURED integration that has failed to sync (or
            # never synced) marks the dashboard "degraded" - one that
            # simply hasn't been set up yet is a neutral, expected state
            # (spec section 28).
            if configured and not connected:
                overall_ok = False

            integrations.append(
                {
                    "key": integration.key,
                    "display_name": integration.display_name,
                    "configured": configured,
                    "connected": connected,
                    "last_sync_at": status.last_sync_at.isoformat()
                    if status and status.last_sync_at
                    else None,
                    "last_error": status.last_error if status else None,
                    "records_synced": status.records_synced if status else 0,
                }
            )

        return {
            "status": "ok" if overall_ok else "degraded",
            "integrations": integrations,
            "ai_enabled": False,  # wired up properly in Phase 7
        }
    finally:
        db.close()
