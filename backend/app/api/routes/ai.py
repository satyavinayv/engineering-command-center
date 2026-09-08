"""
AI endpoints. GET is what the dashboard calls on load - it's always
fast because it either returns the cached briefing or (worst case, if
the scheduler hasn't run yet) triggers one generation. POST /regenerate
is for an explicit "regenerate" button, bypassing the cache on purpose.
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.services.ai_summary import get_or_generate_daily_briefing

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(require_api_key)])


@router.get("/daily-briefing")
def daily_briefing():
    return get_or_generate_daily_briefing(force=False)


@router.post("/daily-briefing/regenerate")
def regenerate_daily_briefing():
    return get_or_generate_daily_briefing(force=True)