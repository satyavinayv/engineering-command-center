"""
Manual sync trigger — useful for the admin screen (spec section 33) and
for verifying an integration works right after configuring credentials,
without waiting for the next scheduled interval.
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.integrations.registry import registry
from app.services.sync_service import run_sync

router = APIRouter(prefix="/api/sync", tags=["sync"], dependencies=[Depends(require_api_key)])


@router.post("/{integration_key}")
def trigger_sync(integration_key: str):
    integration = registry.get(integration_key)
    if not integration:
        return {"error": f"unknown integration '{integration_key}'"}
    if not integration.is_configured():
        return {"error": f"'{integration_key}' is not configured yet"}
    run_sync(integration)
    return {"status": "completed"}
