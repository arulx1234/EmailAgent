import json
import sqlite3
import time
from pathlib import Path
from typing import Any


MAIL_CACHE_DB_FILE = Path(__file__).resolve().parents[2] / ".mail_cache.sqlite3"
MAIL_CACHE_LIMIT = 50
CACHE_REVALIDATION_SECONDS = 5 * 60


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(MAIL_CACHE_DB_FILE, timeout=10)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cached_emails (
            account_email TEXT NOT NULL,
            message_id TEXT NOT NULL,
            received_at INTEGER NOT NULL,
            checked_at REAL NOT NULL,
            email_json TEXT NOT NULL,
            PRIMARY KEY (account_email, message_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS cached_emails_account_received
        ON cached_emails (account_email, received_at DESC)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cached_gmail_labels (
            account_email TEXT NOT NULL,
            label_name TEXT NOT NULL,
            label_id TEXT NOT NULL,
            PRIMARY KEY (account_email, label_name)
        )
        """
    )
    return connection


def get_cached_emails(
    account_email: str,
    message_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not message_ids:
        return {}

    placeholders = ",".join("?" for _ in message_ids)
    connection = _connect()
    try:
        rows = connection.execute(
            f"""
            SELECT message_id, checked_at, email_json
            FROM cached_emails
            WHERE account_email = ? AND message_id IN ({placeholders})
            """,
            (account_email, *message_ids),
        ).fetchall()
    finally:
        connection.close()

    return {
        message_id: {
            "checked_at": checked_at,
            "email": json.loads(email_json),
        }
        for message_id, checked_at, email_json in rows
    }


def get_latest_cached_emails(
    account_email: str,
    max_results: int,
    *,
    category: str | None = None,
    label_ids: list[str] | None = None,
    spam_only: bool = False,
    exclude_spam: bool = False,
) -> list[dict[str, Any]]:
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT email_json
            FROM cached_emails
            WHERE account_email = ?
            ORDER BY received_at DESC, checked_at DESC
            LIMIT ?
            """,
            (account_email, MAIL_CACHE_LIMIT),
        ).fetchall()
    finally:
        connection.close()

    requested_label_ids = set(label_ids or [])
    matching_emails = []
    for (email_json,) in rows:
        email = json.loads(email_json)
        email_label_ids = set(email.get("labels", []))
        if category and (
            email.get("classification", {}).get("category", "").casefold()
            != category.casefold()
        ):
            continue
        if requested_label_ids and not requested_label_ids.issubset(email_label_ids):
            continue
        if spam_only and "SPAM" not in email_label_ids:
            continue
        if exclude_spam and "SPAM" in email_label_ids:
            continue
        matching_emails.append(email)
        if len(matching_emails) == max_results:
            break

    return matching_emails


def has_cached_mailbox(account_email: str) -> bool:
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT 1
            FROM cached_emails
            WHERE account_email = ?
            LIMIT 1
            """,
            (account_email,),
        ).fetchone()
    finally:
        connection.close()
    return row is not None


def get_cached_gmail_label_ids(
    account_email: str,
    label_names: list[str],
) -> dict[str, str]:
    if not label_names:
        return {}

    placeholders = ",".join("?" for _ in label_names)
    connection = _connect()
    try:
        rows = connection.execute(
            f"""
            SELECT label_name, label_id
            FROM cached_gmail_labels
            WHERE account_email = ? AND label_name IN ({placeholders})
            """,
            (account_email, *label_names),
        ).fetchall()
    finally:
        connection.close()

    return dict(rows)


def store_cached_gmail_labels(
    account_email: str,
    labels: list[dict[str, str]],
) -> None:
    if not labels:
        return

    connection = _connect()
    try:
        with connection:
            connection.executemany(
                """
                INSERT INTO cached_gmail_labels (account_email, label_name, label_id)
                VALUES (?, ?, ?)
                ON CONFLICT(account_email, label_name) DO UPDATE SET
                    label_id = excluded.label_id
                """,
                [
                    (account_email, label["name"], label["id"])
                    for label in labels
                    if label.get("name") and label.get("id")
                ],
            )
    finally:
        connection.close()


def delete_cached_gmail_label(account_email: str, label_name: str) -> None:
    connection = _connect()
    try:
        with connection:
            connection.execute(
                "DELETE FROM cached_gmail_labels WHERE account_email = ? AND label_name = ?",
                (account_email, label_name),
            )
    finally:
        connection.close()


def store_cached_emails(
    account_email: str,
    emails: list[tuple[dict[str, Any], int]],
) -> None:
    if not emails:
        return

    now = time.time()
    connection = _connect()
    try:
        with connection:
            connection.executemany(
                """
                INSERT INTO cached_emails
                    (account_email, message_id, received_at, checked_at, email_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_email, message_id) DO UPDATE SET
                    received_at = excluded.received_at,
                    checked_at = excluded.checked_at,
                    email_json = excluded.email_json
                """,
                [
                    (
                        account_email,
                        email["id"],
                        received_at,
                        now,
                        json.dumps(email, ensure_ascii=False),
                    )
                    for email, received_at in emails
                ],
            )
            connection.execute(
                """
                DELETE FROM cached_emails
                WHERE account_email = ?
                  AND message_id NOT IN (
                      SELECT message_id
                      FROM cached_emails
                      WHERE account_email = ?
                      ORDER BY received_at DESC, checked_at DESC
                      LIMIT ?
                  )
                """,
                (account_email, account_email, MAIL_CACHE_LIMIT),
            )
    finally:
        connection.close()


def update_cached_email_labels(
    account_email: str,
    message_id: str,
    labels: list[str],
) -> None:
    connection = _connect()
    try:
        with connection:
            row = connection.execute(
                "SELECT email_json FROM cached_emails WHERE account_email = ? AND message_id = ?",
                (account_email, message_id),
            ).fetchone()
            if row is None:
                return
            email = json.loads(row[0])
            email["labels"] = labels
            connection.execute(
                "UPDATE cached_emails SET email_json = ?, checked_at = ? "
                "WHERE account_email = ? AND message_id = ?",
                (json.dumps(email, ensure_ascii=False), time.time(), account_email, message_id),
            )
    finally:
        connection.close()


def invalidate_cached_emails(
    account_email: str,
    message_ids: list[str],
) -> None:
    if not message_ids:
        return

    placeholders = ",".join("?" for _ in message_ids)
    connection = _connect()
    try:
        with connection:
            connection.execute(
                f"""
                UPDATE cached_emails
                SET checked_at = 0
                WHERE account_email = ? AND message_id IN ({placeholders})
                """,
                (account_email, *message_ids),
            )
    finally:
        connection.close()
