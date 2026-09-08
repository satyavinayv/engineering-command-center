"""
Gmail integration via IMAP + App Password.

Sync strategy:

FIRST SYNC
-----------
Fetch messages from the configured historical window.

INCREMENTAL SYNC
----------------
Use a per-folder IMAP UID cursor and fetch only messages whose UID is
greater than the previously persisted UID.

This prevents every sync from downloading thousands of existing emails.
"""

from __future__ import annotations

import email
import imaplib
import json
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from typing import Any

from app.config import settings
from app.integrations.base import (
    Integration,
    IntegrationAuthError,
    IntegrationConnectionError,
    SyncResult,
)

IMAP_PORT = 993
IMAP_TIMEOUT_SECONDS = 30

# Number of messages in one FETCH request.
FETCH_BATCH_SIZE = 500

# Only fetch a small amount of message text.
SNIPPET_BYTES = 1000


def _decode(value: str | None) -> str:
    if not value:
        return ""

    parts = decode_header(value)
    out = []

    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(
                text.decode(
                    enc or "utf-8",
                    errors="replace",
                )
            )
        else:
            out.append(text)

    return "".join(out)


class GmailIntegration(Integration):
    key = "gmail"
    display_name = "Gmail (IMAP + App Password)"

    def __init__(self) -> None:
        self.host = settings.gmail_imap_host
        self.username = settings.gmail_username
        self.app_password = settings.gmail_app_password
        self.window_days = settings.gmail_sync_window_days
        self.label_folders = settings.gmail_labels_list

    def is_configured(self) -> bool:
        return bool(
            self.username
            and self.app_password
        )

    def _connect(self) -> imaplib.IMAP4_SSL:
        try:
            conn = imaplib.IMAP4_SSL(
                self.host,
                IMAP_PORT,
                timeout=IMAP_TIMEOUT_SECONDS,
            )
        except (
            OSError,
            imaplib.IMAP4.error,
        ) as exc:
            raise IntegrationConnectionError(
                f"Could not reach {self.host}: {exc}"
            ) from exc

        try:
            conn.login(
                self.username,
                self.app_password,
            )
        except imaplib.IMAP4.error as exc:
            try:
                conn.logout()
            except Exception:
                pass

            raise IntegrationAuthError(
                f"Gmail rejected the app password: {exc}"
            ) from exc

        return conn

    def authenticate(self) -> None:
        if not self.is_configured():
            raise IntegrationAuthError(
                "GMAIL_USERNAME / GMAIL_APP_PASSWORD not set"
            )

        conn = self._connect()

        try:
            pass
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def test_connection(self) -> bool:
        try:
            self.authenticate()
            return True
        except (
            IntegrationAuthError,
            IntegrationConnectionError,
        ):
            return False

    def _available_folders(
        self,
        conn: imaplib.IMAP4_SSL,
    ) -> list[str]:
        status, folders = conn.list()

        if status != "OK":
            return []

        names: list[str] = []

        for raw in folders or []:
            if not raw:
                continue

            decoded = raw.decode(
                "utf-8",
                errors="replace",
            )

            if '"' in decoded:
                parts = decoded.split('"')

                if len(parts) >= 3:
                    names.append(parts[-2])

        return names

    def _select_folder(
        self,
        conn: imaplib.IMAP4_SSL,
        folder: str,
    ) -> bool:
        status, _ = conn.select(
            f'"{folder}"',
            readonly=True,
        )

        if status != "OK":
            print(
                f"[GMAIL] Could not select folder: {folder}",
                flush=True,
            )
            return False

        return True

    @staticmethod
    def _parse_uid_search(
        data: list[bytes] | None,
    ) -> list[bytes]:
        if not data or not data[0]:
            return []

        return data[0].split()

    def _search_initial(
        self,
        conn: imaplib.IMAP4_SSL,
        folder: str,
        since: datetime,
    ) -> list[bytes]:
        since_str = since.strftime("%d-%b-%Y")

        status, data = conn.uid(
            "SEARCH",
            None,
            f"SINCE {since_str}",
        )

        if status != "OK":
            return []

        return self._parse_uid_search(data)

    def _search_incremental(
        self,
        conn: imaplib.IMAP4_SSL,
        folder: str,
        last_uid: int,
    ) -> list[bytes]:
        """
        Find only UIDs greater than the previously persisted UID.
        """
        status, data = conn.uid(
            "SEARCH",
            None,
            f"UID {last_uid + 1}:*",
        )

        if status != "OK":
            return []

        return self._parse_uid_search(data)

    @staticmethod
    def _append_parsed_message(
            results: list[dict[str, Any]],
            folder: str,
            header_bytes: bytes,
            flags: list[str],
            uid: int | None,
    ) -> None:
        try:
            msg = email.message_from_bytes(
                header_bytes
            )
        except Exception:
            return

        results.append(
            {
                "folder": folder,
                "message_id": msg.get("Message-ID", "").strip(),
                "uid": uid,
                "subject": _decode(msg.get("Subject")),
                "from_addr": _decode(msg.get("From")),
                "to_addrs": _decode(msg.get("To")),
                "cc_addrs": _decode(msg.get("Cc")),
                "date_raw": msg.get("Date"),
                "unread": "\\Seen" not in flags,
                "snippet": "",
            }
        )

    def _fetch_batch(
            self,
            conn: imaplib.IMAP4_SSL,
            message_uids: list[bytes],
            folder: str,
    ) -> list[dict[str, Any]]:
        if not message_uids:
            return []

        uid_sequence = b",".join(
            message_uids
        ).decode("ascii")

        fetch_command = (
            "(UID "
            "BODY.PEEK[HEADER] "
            "FLAGS)"
        )

        status, msg_data = conn.uid(
            "FETCH",
            uid_sequence,
            fetch_command,
        )

        if status != "OK" or not msg_data:
            return []

        results: list[dict[str, Any]] = []

        current_header = b""
        current_flags: list[str] = []
        current_uid: int | None = None

        for part in msg_data:

            if isinstance(part, tuple) and len(part) == 2:
                meta, content = part

                if not isinstance(meta, bytes):
                    continue

                # Extract UID from FETCH metadata.
                uid = None
                marker = b"UID "

                if marker in meta:
                    try:
                        after_uid = meta.split(
                            marker,
                            1,
                        )[1]

                        uid_text = (
                            after_uid
                            .split(b" ", 1)[0]
                            .rstrip(b")")
                        )

                        uid = int(uid_text)

                    except (ValueError, IndexError):
                        uid = None

                if b"HEADER" in meta:

                    # Finalize previous message.
                    if current_header:
                        self._append_parsed_message(
                            results,
                            folder,
                            current_header,
                            current_flags,
                            current_uid,
                        )

                    # Start new message.
                    current_header = content
                    current_flags = []
                    current_uid = uid

            elif (
                    isinstance(part, bytes)
                    and b"FLAGS" in part
            ):
                parsed_flags = imaplib.ParseFlags(part)

                current_flags = [
                    f.decode(errors="replace")
                    if isinstance(f, bytes)
                    else f
                    for f in parsed_flags
                ]

        # Final message.
        if current_header:
            self._append_parsed_message(
                results,
                folder,
                current_header,
                current_flags,
                current_uid,
            )

        return results

    def _fetch_folder(
        self,
        conn: imaplib.IMAP4_SSL,
        folder: str,
        since: datetime | None = None,
        last_uid: int | None = None,
    ) -> tuple[list[dict[str, Any]], int | None]:

        folder_start = time.perf_counter()

        if not self._select_folder(
            conn,
            folder,
        ):
            return [], last_uid

        search_start = time.perf_counter()

        if last_uid is None:
            message_uids = self._search_initial(
                conn,
                folder,
                since or (
                    datetime.now(timezone.utc)
                    - timedelta(
                        days=self.window_days
                    )
                ),
            )
        else:
            message_uids = self._search_incremental(
                conn,
                folder,
                last_uid,
            )

        search_elapsed = (
            time.perf_counter()
            - search_start
        )

        print(
            f"[GMAIL] {folder}: "
            f"{len(message_uids)} messages "
            f"(search {search_elapsed:.2f}s)",
            flush=True,
        )

        if not message_uids:
            return [], last_uid

        results: list[dict[str, Any]] = []

        fetch_start = time.perf_counter()

        highest_uid = last_uid

        for start in range(
            0,
            len(message_uids),
            FETCH_BATCH_SIZE,
        ):
            batch = message_uids[
                start:start
                + FETCH_BATCH_SIZE
            ]

            batch_number = (
                start // FETCH_BATCH_SIZE
            ) + 1

            print(
                f"[GMAIL] {folder}: "
                f"fetching batch "
                f"{batch_number} "
                f"({len(batch)} messages)",
                flush=True,
            )

            try:
                batch_results = (
                    self._fetch_batch(
                        conn,
                        batch,
                        folder,
                    )
                )

                results.extend(
                    batch_results
                )

                for message in batch_results:
                    uid = message.get(
                        "uid"
                    )

                    if (
                        isinstance(uid, int)
                        and (
                            highest_uid is None
                            or uid > highest_uid
                        )
                    ):
                        highest_uid = uid

            except (
                imaplib.IMAP4.error,
                OSError,
            ) as exc:
                print(
                    f"[GMAIL] {folder}: "
                    f"batch {batch_number} "
                    f"failed: {exc}",
                    flush=True,
                )

        fetch_elapsed = (
            time.perf_counter()
            - fetch_start
        )

        folder_elapsed = (
            time.perf_counter()
            - folder_start
        )

        print(
            f"[GMAIL] {folder}: "
            f"fetched {len(results)} "
            f"messages in "
            f"{fetch_elapsed:.2f}s "
            f"(total "
            f"{folder_elapsed:.2f}s)",
            flush=True,
        )

        return results, highest_uid

    def _sync(
        self,
        window_days: int,
        cursor: dict[str, int] | None = None,
    ) -> SyncResult:

        from app.services.gmail_sync import (
            persist_messages,
        )

        sync_start = time.perf_counter()

        print(
            f"[GMAIL] Sync started "
            f"(window={window_days} days)",
            flush=True,
        )

        conn = self._connect()

        try:
            available = (
                self._available_folders(
                    conn
                )
            )

            folders_to_check = [
                "INBOX"
            ]

            for label in self.label_folders:
                if (
                    label in available
                    and label not in folders_to_check
                ):
                    folders_to_check.append(
                        label
                    )

            print(
                f"[GMAIL] Available folders: "
                f"{len(available)}",
                flush=True,
            )

            print(
                f"[GMAIL] Syncing folders: "
                f"{folders_to_check}",
                flush=True,
            )

            all_messages: list[
                dict[str, Any]
            ] = []

            new_cursor: dict[str, int] = {}

            initial_sync = not bool(cursor)

            for folder in folders_to_check:

                folder_last_uid = None

                if cursor:
                    folder_last_uid = (
                        cursor.get(folder)
                    )

                if initial_sync:
                    print(
                        f"[GMAIL] {folder}: "
                        f"initial sync",
                        flush=True,
                    )
                else:
                    print(
                        f"[GMAIL] {folder}: "
                        f"incremental sync "
                        f"(last UID="
                        f"{folder_last_uid})",
                        flush=True,
                    )

                folder_messages, highest_uid = (
                    self._fetch_folder(
                        conn,
                        folder,
                        (
                            datetime.now(
                                timezone.utc
                            )
                            - timedelta(
                                days=window_days
                            )
                        )
                        if initial_sync
                        else None,
                        folder_last_uid,
                    )
                )

                all_messages.extend(
                    folder_messages
                )

                if highest_uid is not None:
                    new_cursor[
                        folder
                    ] = highest_uid
                elif folder_last_uid is not None:
                    new_cursor[
                        folder
                    ] = folder_last_uid

        finally:
            try:
                conn.logout()
            except Exception:
                pass

        print(
            f"[GMAIL] Total messages fetched: "
            f"{len(all_messages)}",
            flush=True,
        )

        persist_start = time.perf_counter()

        result = persist_messages(
            all_messages
        )

        persist_elapsed = (
            time.perf_counter()
            - persist_start
        )

        total_elapsed = (
            time.perf_counter()
            - sync_start
        )

        print(
            f"[GMAIL] Persist completed in "
            f"{persist_elapsed:.2f}s",
            flush=True,
        )

        print(
            f"[GMAIL] Sync completed in "
            f"{total_elapsed:.2f}s | "
            f"new={result['new']} "
            f"updated={result['updated']}",
            flush=True,
        )

        return SyncResult(
            records_fetched=len(
                all_messages
            ),
            records_new=result["new"],
            records_updated=result["updated"],
            cursor=json.dumps(
                new_cursor
            ),
        )

    def fetch_initial_data(
        self,
        window_days: int | None = None,
    ) -> SyncResult:

        return self._sync(
            window_days
            or self.window_days,
            cursor=None,
        )

    def incremental_sync(
        self,
        cursor: str | None,
    ) -> SyncResult:

        parsed_cursor: dict[
            str, int
        ] = {}

        if cursor:
            try:
                parsed = json.loads(cursor)

                if isinstance(
                    parsed,
                    dict,
                ):
                    parsed_cursor = {
                        str(folder): int(uid)
                        for folder, uid
                        in parsed.items()
                    }

            except (
                ValueError,
                TypeError,
            ):
                print(
                    "[GMAIL] Invalid cursor; "
                    "falling back to "
                    "initial sync",
                    flush=True,
                )

        return self._sync(
            self.window_days,
            cursor=parsed_cursor,
        )

    def get_item(
        self,
        item_id: str,
    ) -> dict[str, Any] | None:

        from app.database import (
            SessionLocal,
        )
        from app.models import EmailMessage

        db = SessionLocal()

        try:
            row = (
                db.query(
                    EmailMessage
                )
                .filter(
                    EmailMessage.message_id
                    == item_id
                )
                .first()
            )

            return (
                _serialize(row)
                if row
                else None
            )

        finally:
            db.close()

    def search(
        self,
        query: str,
    ) -> list[dict[str, Any]]:

        from app.database import (
            SessionLocal,
        )
        from app.models import EmailMessage

        db = SessionLocal()

        try:
            like = f"%{query}%"

            rows = (
                db.query(
                    EmailMessage
                )
                .filter(
                    (
                        EmailMessage.subject
                        .ilike(like)
                    )
                    | (
                        EmailMessage.from_addr
                        .ilike(like)
                    )
                )
                .order_by(
                    EmailMessage.received_at.desc()
                )
                .limit(25)
                .all()
            )

            return [
                _serialize(row)
                for row in rows
            ]

        finally:
            db.close()


def _serialize(row) -> dict[str, Any]:
    return {
        "message_id": row.message_id,
        "folder": row.folder,
        "subject": row.subject,
        "from_addr": row.from_addr,
        "unread": row.unread,
        "is_addressed_to_me": (
            row.is_addressed_to_me
        ),
        "is_cc": row.is_cc,
        "from_important_sender": (
            row.from_important_sender
        ),
        "related_jira_keys": (
            row.related_jira_keys
        ),
        "related_gitlab_refs": (
            row.related_gitlab_refs
        ),
        "action_required": (
            row.action_required
        ),
        "received_at": (
            row.received_at.isoformat()
            if row.received_at
            else None
        ),
    }