"""
Deterministic parsing + classification for Gmail messages (Phase 5).

No AI involved. Everything here is regex/rule-based metadata sitting
alongside the raw email — spec section 5's "Important/Action Required/
FYI/Low Priority" AI classification is a Phase 7 addition on top of
this, never a replacement for it.

Persistence uses Gmail's Message-ID as the global deduplication key.

Important:
A Gmail message can appear in multiple labels/folders. Therefore the
same Message-ID may occur multiple times in one sync batch.

Incoming messages are deduplicated before persistence so SQLite never
receives multiple INSERTs for the same unique Message-ID.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from app.config import settings
from app.database import SessionLocal
from app.models import EmailMessage


JIRA_KEY_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9]{1,9}-\d+\b"
)

GITLAB_MR_PATTERN = re.compile(
    r"https?://[^\s]+/-/merge_requests/\d+"
)

GITLAB_ISSUE_PATTERN = re.compile(
    r"https?://[^\s]+/-/issues/\d+"
)


def _addr_matches(
    header_value: str,
    email_addr: str,
) -> bool:
    if not header_value or not email_addr:
        return False

    return email_addr.lower() in header_value.lower()


def _from_important_sender(
    from_addr: str,
) -> bool:
    for entry in settings.gmail_important_senders_list:
        if entry.lower() in from_addr.lower():
            return True

    return False


def _parse_date(
    date_raw: str | None,
) -> datetime | None:
    """
    Return naive UTC.

    This matches the convention used elsewhere in the codebase,
    including calendar_sync.py.
    """
    if not date_raw:
        return None

    try:
        parsed = parsedate_to_datetime(date_raw)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo:
        return parsed.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    return parsed


def _build_fields(
    msg: dict,
) -> dict:
    """
    Build deterministic metadata fields for one Gmail message.
    """

    subject = msg.get("subject", "")
    snippet = msg.get("snippet", "")

    search_text = f"{subject} {snippet}"

    jira_keys = sorted(
        set(
            JIRA_KEY_PATTERN.findall(
                search_text
            )
        )
    )

    has_mr_link = bool(
        GITLAB_MR_PATTERN.search(
            search_text
        )
    )

    has_gitlab_issue_link = bool(
        GITLAB_ISSUE_PATTERN.search(
            search_text
        )
    )

    to_addrs = msg.get(
        "to_addrs",
        "",
    )

    cc_addrs = msg.get(
        "cc_addrs",
        "",
    )

    from_addr = msg.get(
        "from_addr",
        "",
    )

    unread = bool(
        msg.get("unread")
    )

    is_addressed_to_me = _addr_matches(
        to_addrs,
        settings.gmail_username,
    )

    is_cc = _addr_matches(
        cc_addrs,
        settings.gmail_username,
    )

    from_important = _from_important_sender(
        from_addr
    )

    # Deterministic floor.
    #
    # This is NOT the Phase 7 AI classifier.
    # It simply identifies unread messages addressed
    # directly to the configured Gmail user.
    action_required = (
        unread
        and is_addressed_to_me
    )

    return {
        "folder": msg.get(
            "folder",
            "",
        ),
        "subject": subject,
        "from_addr": from_addr,
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "unread": unread,
        "is_addressed_to_me": (
            is_addressed_to_me
        ),
        "is_cc": is_cc,
        "from_important_sender": (
            from_important
        ),
        "related_jira_keys": ",".join(
            jira_keys
        ),
        "related_gitlab_refs": (
            "mr"
            if has_mr_link
            else (
                "issue"
                if has_gitlab_issue_link
                else ""
            )
        ),
        "action_required": (
            action_required
        ),
        "snippet": snippet[:500],
        "received_at": _parse_date(
            msg.get("date_raw")
        ),
        "last_synced_at": datetime.now(
            timezone.utc
        ),
    }


def persist_messages(
    messages: list[dict],
) -> dict:
    """
    Persist Gmail messages using Message-ID as the global
    deduplication key.

    A single Gmail message may exist in multiple labels/folders.

    Example:

        INBOX      -> Message-ID <abc@gmail.com>
        Jira_Admin -> Message-ID <abc@gmail.com>

    Gmail can therefore return the same Message-ID multiple times
    during one sync.

    We first deduplicate the incoming batch, then load existing
    database rows in one query, and finally update/insert rows.

    This prevents multiple pending INSERTs for the same unique
    Message-ID from reaching SQLite in the same transaction.
    """

    db = SessionLocal()

    try:
        # ------------------------------------------------------------
        # 1. Deduplicate incoming messages.
        # ------------------------------------------------------------
        unique_messages: dict[
            str,
            dict,
        ] = {}

        for msg in messages:
            message_id = (
                msg.get("message_id")
                or ""
            ).strip()

            if not message_id:
                # Cannot safely deduplicate without a Message-ID.
                # Skip instead of inventing one.
                continue

            # Keep one copy of each Message-ID.
            #
            # If the same message appears in multiple folders,
            # prefer the INBOX copy because it is generally the
            # canonical user-facing location.
            existing_message = unique_messages.get(
                message_id
            )

            if existing_message is None:
                unique_messages[
                    message_id
                ] = msg

            elif (
                existing_message.get("folder")
                != "INBOX"
                and msg.get("folder")
                == "INBOX"
            ):
                unique_messages[
                    message_id
                ] = msg

        if len(unique_messages) != len(messages):
            skipped_duplicates = (
                len(messages)
                - len(unique_messages)
            )

            print(
                "[GMAIL] Removed "
                f"{skipped_duplicates} "
                "duplicate Message-ID(s) "
                "before DB persistence",
                flush=True,
            )

        if not unique_messages:
            return {
                "new": 0,
                "updated": 0,
            }

        # ------------------------------------------------------------
        # 2. Fetch existing database rows in one query.
        # ------------------------------------------------------------
        message_ids = list(
            unique_messages.keys()
        )

        existing_rows = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.message_id.in_(
                    message_ids
                )
            )
            .all()
        )

        existing_by_id = {
            row.message_id: row
            for row in existing_rows
        }

        new_count = 0
        updated_count = 0

        # ------------------------------------------------------------
        # 3. Update existing rows / insert new rows.
        # ------------------------------------------------------------
        for (
            message_id,
            msg,
        ) in unique_messages.items():

            fields = _build_fields(msg)

            existing = existing_by_id.get(
                message_id
            )

            if existing:
                for key, value in fields.items():
                    setattr(
                        existing,
                        key,
                        value,
                    )

                updated_count += 1

            else:
                db.add(
                    EmailMessage(
                        message_id=message_id,
                        **fields,
                    )
                )

                new_count += 1

        # ------------------------------------------------------------
        # 4. Commit the complete batch.
        # ------------------------------------------------------------
        db.commit()

        return {
            "new": new_count,
            "updated": updated_count,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()