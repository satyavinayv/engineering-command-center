"""
Deterministic parsing + classification for Gmail messages (Phase 5).
No AI involved. Everything here is regex/rule-based metadata sitting
alongside the raw email — spec section 5's "Important/Action Required/
FYI/Low Priority" AI classification is a Phase 7 addition on top of
this, never a replacement for it.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from app.config import settings
from app.database import SessionLocal
from app.models import EmailMessage

JIRA_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")
GITLAB_MR_PATTERN = re.compile(r"https?://[^\s]+/-/merge_requests/\d+")
GITLAB_ISSUE_PATTERN = re.compile(r"https?://[^\s]+/-/issues/\d+")


def _addr_matches(header_value: str, email_addr: str) -> bool:
    if not header_value or not email_addr:
        return False
    return email_addr.lower() in header_value.lower()


def _from_important_sender(from_addr: str) -> bool:
    for entry in settings.gmail_important_senders_list:
        if entry.lower() in from_addr.lower():
            return True
    return False


def _parse_date(date_raw: str | None) -> datetime | None:
    """Returns naive UTC, matching the convention used everywhere else
    in this codebase (see the same normalization in calendar_sync.py)."""
    if not date_raw:
        return None
    try:
        parsed = parsedate_to_datetime(date_raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def persist_messages(messages: list[dict]) -> dict:
    db = SessionLocal()
    new_count = 0
    updated_count = 0

    try:
        for msg in messages:
            message_id = msg["message_id"]
            if not message_id:
                continue  # can't dedupe without one; skip rather than guess

            search_text = f"{msg['subject']} {msg['snippet']}"
            jira_keys = sorted(set(JIRA_KEY_PATTERN.findall(search_text)))
            has_mr_link = bool(GITLAB_MR_PATTERN.search(search_text))
            has_gitlab_issue_link = bool(GITLAB_ISSUE_PATTERN.search(search_text))

            is_addressed_to_me = _addr_matches(msg["to_addrs"], settings.gmail_username)
            is_cc = _addr_matches(msg["cc_addrs"], settings.gmail_username)
            from_important = _from_important_sender(msg["from_addr"])

            # Coarse deterministic proxy, not a real classifier: unread
            # AND addressed directly (not just cc'd). Phase 7's AI
            # classification refines this later — this is the
            # always-available deterministic floor spec section 5
            # requires.
            action_required = msg["unread"] and is_addressed_to_me

            existing = db.query(EmailMessage).filter(EmailMessage.message_id == message_id).first()
            fields = dict(
                folder=msg["folder"],
                subject=msg["subject"],
                from_addr=msg["from_addr"],
                to_addrs=msg["to_addrs"],
                cc_addrs=msg["cc_addrs"],
                unread=msg["unread"],
                is_addressed_to_me=is_addressed_to_me,
                is_cc=is_cc,
                from_important_sender=from_important,
                related_jira_keys=",".join(jira_keys),
                related_gitlab_refs="mr" if has_mr_link else ("issue" if has_gitlab_issue_link else ""),
                action_required=action_required,
                snippet=msg["snippet"][:500],
                received_at=_parse_date(msg["date_raw"]),
            )

            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated_count += 1
            else:
                db.add(EmailMessage(message_id=message_id, **fields))
                new_count += 1

        db.commit()
    finally:
        db.close()

    return {"new": new_count, "updated": updated_count}