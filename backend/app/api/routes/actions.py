"""
The unified "Action Required" feed - spec section 15, described as
"the most important section of the dashboard." Pure aggregation over
already-synced data (see action_engine.py); no live external calls, no
AI. AI (Phase 7) only ever summarizes what this endpoint already
computed - it never decides priority itself.
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.services.action_engine import get_action_items

router = APIRouter(prefix="/api/actions", tags=["actions"], dependencies=[Depends(require_api_key)])


@router.get("/required")
def action_required():
    """P0-P2 only - things that actually need a response."""
    return [i.to_dict() for i in get_action_items(include_p3=False)]


@router.get("/feed")
def unified_feed():
    """Everything, including P3/informational - the broader activity
    feed from spec section 14."""
    return [i.to_dict() for i in get_action_items(include_p3=True)]