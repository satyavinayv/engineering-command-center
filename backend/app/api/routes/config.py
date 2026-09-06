"""
Configuration endpoint. Phase 1 exposes read-only, non-secret settings
(sync intervals, which integrations are enabled) so the admin screen
(spec section 33) has something to render. Editable config + secrets
management comes with the integrations that need it.
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.config import settings
from app.integrations.registry import registry

router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(require_api_key)])


@router.get("")
def get_config():
    return {
        "app_env": settings.app_env,
        "ai_enabled": settings.ai_enabled,
        "sync_intervals_minutes": {
            "gmail": settings.sync_interval_gmail,
            "calendar": settings.sync_interval_calendar,
            "jira": settings.sync_interval_jira,
            "gitlab": settings.sync_interval_gitlab,
            "opensearch": settings.sync_interval_opensearch,
        },
        "integrations": [
            {"key": i.key, "display_name": i.display_name, "configured": i.is_configured()}
            for i in registry.all()
        ],
    }


@router.post("/test-connection/{integration_key}")
def test_connection(integration_key: str):
    """Deliberate, on-demand live check - the one place in the app that's
    allowed to hit an external API synchronously on a user request,
    since the user explicitly asked "is this working right now?" rather
    than just loading the dashboard."""
    integration = registry.get(integration_key)
    if not integration:
        return {"error": f"unknown integration '{integration_key}'"}
    if not integration.is_configured():
        return {"key": integration_key, "configured": False, "connected": False}
    status = integration.health_check()
    return {
        "key": integration_key,
        "configured": True,
        "connected": status.connected,
        "last_error": status.last_error,
    }
