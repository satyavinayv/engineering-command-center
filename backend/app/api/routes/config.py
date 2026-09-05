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
