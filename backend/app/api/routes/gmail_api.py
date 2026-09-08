"""
Gmail API endpoints (Phase 5). Read-only from DB — the backend's
background sync (or manual /api/sync/gmail trigger) is what talks to
IMAP; the dashboard never does (spec section 36).

Wire this in wherever main.py includes the jira/gitlab/calendar
routers:
    from app.api.gmail import router as gmail_router
    app.include_router(gmail_router)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.database import SessionLocal
from app.models import EmailMessage

router = APIRouter(prefix="/api/gmail", tags=["gmail"], dependencies=[Depends(require_api_key)])


@router.get("/messages")
def list_messages(folder: str | None = None, limit: int = 100) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(EmailMessage)
        if folder:
            query = query.filter(EmailMessage.folder == folder)
        rows = query.order_by(EmailMessage.received_at.desc()).limit(limit).all()
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/unread")
def unread() -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(EmailMessage)
            .filter(EmailMessage.unread.is_(True))
            .order_by(EmailMessage.received_at.desc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/action-required")
def action_required() -> list[dict]:
    """Deterministic floor per spec section 5 — unread + addressed
    directly to you. Phase 7's AI classification will refine this
    further; this endpoint keeps working with or without AI enabled."""
    db = SessionLocal()
    try:
        rows = (
            db.query(EmailMessage)
            .filter(EmailMessage.action_required.is_(True))
            .order_by(EmailMessage.received_at.desc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/related-jira")
def related_jira() -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(EmailMessage)
            .filter(EmailMessage.related_jira_keys != "")
            .order_by(EmailMessage.received_at.desc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/related-gitlab")
def related_gitlab() -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(EmailMessage)
            .filter(EmailMessage.related_gitlab_refs != "")
            .order_by(EmailMessage.received_at.desc())
            .all()
        )
        return [_serialize(r) for r in rows]
    finally:
        db.close()


def _serialize(row: EmailMessage) -> dict:
    return {
        "message_id": row.message_id,
        "folder": row.folder,
        "subject": row.subject,
        "from_addr": row.from_addr,
        "unread": row.unread,
        "is_addressed_to_me": row.is_addressed_to_me,
        "is_cc": row.is_cc,
        "from_important_sender": row.from_important_sender,
        "related_jira_keys": row.related_jira_keys.split(",") if row.related_jira_keys else [],
        "related_gitlab_refs": row.related_gitlab_refs,
        "action_required": row.action_required,
        "snippet": row.snippet,
        "received_at": row.received_at.isoformat() if row.received_at else None,
    }