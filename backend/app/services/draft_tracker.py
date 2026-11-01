from collections.abc import Generator
from contextlib import contextmanager
import sqlite3
import time
from pathlib import Path


AUTH_DB_FILE = Path(__file__).resolve().parents[2] / ".auth_sessions.sqlite3"
STALE_CLAIM_SECONDS = 15 * 60


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(AUTH_DB_FILE, timeout=10)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reply_draft_processing (
            account_email TEXT NOT NULL,
            message_id TEXT NOT NULL,
            status TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (account_email, message_id)
        )
        """
    )
    return connection


@contextmanager
def _connection() -> Generator[sqlite3.Connection, None, None]:
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def claim_message(account_email: str, message_id: str) -> bool:
    now = time.time()
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            UPDATE reply_draft_processing
            SET status = 'pending', updated_at = ?
            WHERE account_email = ? AND message_id = ?
                AND status = 'processing' AND updated_at <= ?
            """,
            (
                now,
                account_email,
                message_id,
                now - STALE_CLAIM_SECONDS,
            ),
        )
        row = connection.execute(
            """
            SELECT status FROM reply_draft_processing
            WHERE account_email = ? AND message_id = ?
            """,
            (account_email, message_id),
        ).fetchone()
        if row is None:
            connection.execute(
                """
                INSERT INTO reply_draft_processing
                    (account_email, message_id, status, updated_at)
                VALUES (?, ?, 'processing', ?)
                """,
                (account_email, message_id, now),
            )
            return True
        if row[0] != "pending":
            return False

        connection.execute(
            """
            UPDATE reply_draft_processing
            SET status = 'processing', updated_at = ?
            WHERE account_email = ? AND message_id = ? AND status = 'pending'
            """,
            (now, account_email, message_id),
        )
        return True


def complete_message(account_email: str, message_id: str) -> None:
    with _connection() as connection:
        connection.execute(
            """
            UPDATE reply_draft_processing
            SET status = 'complete', updated_at = ?
            WHERE account_email = ? AND message_id = ?
            """,
            (time.time(), account_email, message_id),
        )


def release_message(account_email: str, message_id: str) -> None:
    with _connection() as connection:
        connection.execute(
            """
            UPDATE reply_draft_processing
            SET status = 'pending', updated_at = ?
            WHERE account_email = ? AND message_id = ?
                AND status = 'processing'
            """,
            (time.time(), account_email, message_id),
        )
