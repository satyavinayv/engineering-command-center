"""
AI endpoints. GET is what the dashboard calls on load - it must NEVER
block on an LLM call, so it only ever reads whatever is already
cached (or an "unavailable" shape if nothing has been generated yet).
Actual generation happens in the background scheduler
(_ai_summary_job, spec section 18) or via the explicit POST
/regenerate endpoint below, never inline with a GET.
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.services.ai_summary import get_cached_daily_briefing, get_or_generate_daily_briefing

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(require_api_key)])


@router.get("/daily-briefing")
def daily_briefing():
    return get_cached_daily_briefing()


@router.post("/daily-briefing/regenerate")
def regenerate_daily_briefing():
    return get_or_generate_daily_briefing(force=True)