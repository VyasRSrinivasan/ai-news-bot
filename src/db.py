"""
User subscription database (SQLite).

Stores which news channels each Telegram user has opted into.
"""
import os
import sqlite3
from typing import Dict, List, Set

DB_PATH = os.getenv("DB_PATH", "data/subscriptions.db")


class Database:
    def __init__(self, path: str = DB_PATH):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id     TEXT NOT NULL,
                    channel_key TEXT NOT NULL,
                    PRIMARY KEY (chat_id, channel_key)
                )
            """)

    # ── read ──────────────────────────────────────────────────────────────────

    def get_user_channels(self, chat_id: str) -> Set[str]:
        """Return the set of channel keys the user is subscribed to."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT channel_key FROM subscriptions WHERE chat_id = ?", (chat_id,)
            ).fetchall()
        return {r[0] for r in rows}

    def get_subscribers(self, channel_key: str) -> List[str]:
        """Return all chat_ids subscribed to the given channel key."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT chat_id FROM subscriptions WHERE channel_key = ?", (channel_key,)
            ).fetchall()
        return [r[0] for r in rows]

    def get_all_subscriptions(self) -> Dict[str, Set[str]]:
        """Return {chat_id: {channel_key, ...}} for every user."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT chat_id, channel_key FROM subscriptions"
            ).fetchall()
        result: Dict[str, Set[str]] = {}
        for chat_id, channel_key in rows:
            result.setdefault(chat_id, set()).add(channel_key)
        return result

    # ── write ─────────────────────────────────────────────────────────────────

    def add_channel(self, chat_id: str, channel_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO subscriptions VALUES (?, ?)", (chat_id, channel_key)
            )

    def remove_channel(self, chat_id: str, channel_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM subscriptions WHERE chat_id = ? AND channel_key = ?",
                (chat_id, channel_key),
            )

    def clear_user(self, chat_id: str) -> None:
        """Remove all subscriptions for a user."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,)
            )
