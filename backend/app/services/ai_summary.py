"""
AI daily briefing service.

The AI never reads Gmail, Calendar, Jira, GitLab, or test data directly.
It receives only the already-prioritized Action Engine output.

Briefings are cached by a hash of the action-item list. If nothing that
matters to the briefing has changed, no new AI request is made.
"""

import hashlib
import json

from app.ai.context_builder import build_daily_briefing_prompt
from app.ai.provider import get_ai_provider
from app.database import SessionLocal
from app.models import AISummary
from app.services.action_engine import get_action_items


def _input_hash(action_items: list[dict]) -> str:
    """
    Create a stable hash from the information the AI is allowed to use.

    Do not include descriptions, email bodies, or other potentially
    sensitive/raw content here.
    """
    compact = [
        {
            "source": item.get("source"),
            "priority": item.get("priority"),
            "title": item.get("title"),
            "key": item.get("key"),
        }
        for item in action_items
    ]

    payload = json.dumps(
        compact,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_daily_briefing() -> dict:
    """
    Non-blocking read for the dashboard (GET /api/ai/daily-briefing).

    Never calls the AI provider, regardless of whether the cached
    input_hash is stale relative to the current action items - a
    slightly-stale cached briefing is fine; a dashboard load that
    blocks on an LLM call is not (spec section 18). Generation is the
    background scheduler's job (_ai_summary_job) or the explicit
    POST /api/ai/daily-briefing/regenerate endpoint.

    Returns the same shape as get_or_generate_daily_briefing() so the
    frontend contract doesn't change: {available, content,
    generated_by, created_at, cached}.
    """
    db = SessionLocal()
    try:
        cached = (
            db.query(AISummary)
            .filter(AISummary.kind == "daily_briefing")
            .order_by(AISummary.created_at.desc())
            .first()
        )

        if not cached:
            return {
                "available": False,
                "content": None,
                "generated_by": None,
                "created_at": None,
                "cached": False,
            }

        return {
            "available": True,
            "content": cached.content,
            "generated_by": cached.generated_by,
            "created_at": cached.created_at.isoformat() if cached.created_at else None,
            "cached": True,
        }
    finally:
        db.close()


def get_or_generate_daily_briefing(force: bool = False) -> dict:
    """
    Return the cached daily briefing when possible.

    If force=True, generate a fresh briefing even when the input has not
    changed.

    If AI is disabled/unconfigured, return a non-error response so that
    the dashboard continues working normally.
    """

    # Get the already-computed action feed.
    action_items = [
        item.to_dict()
        for item in get_action_items(include_p3=False)
    ]

    current_hash = _input_hash(action_items)

    db = SessionLocal()

    try:
        cached = (
            db.query(AISummary)
            .filter(AISummary.kind == "daily_briefing")
            .order_by(AISummary.created_at.desc())
            .first()
        )

        # Cache hit.
        if (
            cached
            and not force
            and cached.input_hash == current_hash
        ):
            return {
                "available": True,
                "content": cached.content,
                "generated_by": cached.generated_by,
                "created_at": cached.created_at.isoformat()
                if cached.created_at
                else None,
                "cached": True,
            }

        provider = get_ai_provider()

        # AI disabled or unavailable.
        if provider is None:
            return {
                "available": False,
                "content": None,
                "generated_by": None,
                "created_at": None,
                "cached": False,
            }

        prompt = build_daily_briefing_prompt(action_items)

        content = provider.generate(prompt)

        generated_by = provider.__class__.__name__

        summary = AISummary(
            kind="daily_briefing",
            content=content,
            input_hash=current_hash,
            generated_by=generated_by,
        )

        db.add(summary)
        db.commit()
        db.refresh(summary)

        return {
            "available": True,
            "content": summary.content,
            "generated_by": summary.generated_by,
            "created_at": summary.created_at.isoformat()
            if summary.created_at
            else None,
            "cached": False,
        }

    finally:
        db.close()