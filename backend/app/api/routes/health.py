"""
Deterministic health endpoint (spec section 29 - System Health page).
No AI involved here — purely integration.health_check() results plus
whatever's recorded in the sync_status table.

Left unauthenticated (unlike other routes) since it's low-sensitivity
status info and the frontend dashboard shell needs it before any other
call.
"""
from fastapi import APIRouter

from app.integrations.registry import registry

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health():
    integrations = []
    overall_ok = True
    for integration in registry.all():
        status = integration.health_check()
        if not status.connected:
            overall_ok = False
        integrations.append(
            {
                "key": status.key,
                "display_name": getattr(integration, "display_name", status.key),
                "connected": status.connected,
                "last_sync_at": status.last_sync_at.isoformat() if status.last_sync_at else None,
                "last_error": status.last_error,
                "records_synced": status.records_synced,
            }
        )
    return {
        "status": "ok" if overall_ok else "degraded",
        "integrations": integrations,
        "ai_enabled": False,  # wired up properly in Phase 7
    }
