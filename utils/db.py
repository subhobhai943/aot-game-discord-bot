"""SQLite persistence layer for ODM Striker.

Provides a thin async wrapper (via run_in_executor) so all DB I/O
happens off the event loop without requiring an extra dependency.

Tables
------
players       — per-user RPG stats (level, xp, wins, losses, kills, coins)
player_titans — titan collection (one row per titan per player)
guild_settings — per-guild config (prefix, spawn_channel)
"""
from __future__ import annotations

import asyncio
import sqlite3
import os
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "data/odmstriker.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            user_id     TEXT PRIMARY KEY,
            username    TEXT NOT NULL,
            scout_name  TEXT NOT NULL DEFAULT 'Eren Yeager',
            level       INTEGER NOT NULL DEFAULT 1,
            xp          INTEGER NOT NULL DEFAULT 0,
            wins        INTEGER NOT NULL DEFAULT 0,
            losses      INTEGER NOT NULL DEFAULT 0,
            kills       INTEGER NOT NULL DEFAULT 0,
            coins       INTEGER NOT NULL DEFAULT 0,
            active_titan TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS player_titans (
            user_id     TEXT NOT NULL,
            titan_name  TEXT NOT NULL,
            count       INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (user_id, titan_name),
            FOREIGN KEY (user_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id       TEXT PRIMARY KEY,
            prefix         TEXT NOT NULL DEFAULT '>',
            spawn_channel  INTEGER
        );
    """)
    conn.commit()


class Database:
    """Async-safe SQLite helper. Call `await Database.init()` once at startup."""

    _conn: Optional[sqlite3.Connection] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None

    # ── lifecycle ─────────────────────────────────────────────────────────
    @classmethod
    async def init(cls) -> None:
        """Open DB and create tables (idempotent)."""
        loop = asyncio.get_running_loop()
        cls._loop = loop
        cls._conn = await loop.run_in_executor(None, _get_conn)
        await loop.run_in_executor(None, _init_db, cls._conn)

    @classmethod
    def _run(cls, fn, *args):
        """Run a blocking DB function in the executor."""
        return cls._loop.run_in_executor(None, fn, *args)

    # ── guild settings ────────────────────────────────────────────────────
    @classmethod
    async def get_prefix(cls, guild_id: int) -> str:
        def _q(conn):
            row = conn.execute(
                "SELECT prefix FROM guild_settings WHERE guild_id = ?",
                (str(guild_id),)
            ).fetchone()
            return row["prefix"] if row else ">"
        return await cls._run(_q, cls._conn)

    @classmethod
    async def set_prefix(cls, guild_id: int, prefix: str) -> None:
        def _q(conn):
            conn.execute(
                "INSERT INTO guild_settings (guild_id, prefix) VALUES (?, ?)"
                "  ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix",
                (str(guild_id), prefix)
            )
            conn.commit()
        await cls._run(_q, cls._conn)

    @classmethod
    async def get_spawn_channel(cls, guild_id: int) -> Optional[int]:
        def _q(conn):
            row = conn.execute(
                "SELECT spawn_channel FROM guild_settings WHERE guild_id = ?",
                (str(guild_id),)
            ).fetchone()
            return row["spawn_channel"] if row else None
        return await cls._run(_q, cls._conn)

    @classmethod
    async def set_spawn_channel(cls, guild_id: int, channel_id: int) -> None:
        def _q(conn):
            conn.execute(
                "INSERT INTO guild_settings (guild_id, spawn_channel) VALUES (?, ?)"
                "  ON CONFLICT(guild_id) DO UPDATE SET spawn_channel = excluded.spawn_channel",
                (str(guild_id), channel_id)
            )
            conn.commit()
        await cls._run(_q, cls._conn)

    # ── players ───────────────────────────────────────────────────────────
    @classmethod
    async def get_player(cls, user_id: str, username: str) -> dict:
        """Fetch player row, inserting a default row if not found."""
        def _q(conn):
            row = conn.execute(
                "SELECT * FROM players WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT OR IGNORE INTO players (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM players WHERE user_id = ?", (user_id,)
                ).fetchone()
            titans = conn.execute(
                "SELECT titan_name, count FROM player_titans WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            return dict(row), {t["titan_name"]: t["count"] for t in titans}
        player, collection = await cls._run(_q, cls._conn)
        player["collection"] = collection
        return player

    @classmethod
    async def save_player(cls, player_data: dict) -> None:
        """Upsert player row and sync titan collection."""
        collection = player_data.pop("collection", {})

        def _q(conn):
            conn.execute(
                """
                INSERT INTO players
                    (user_id, username, scout_name, level, xp, wins, losses, kills, coins, active_titan)
                VALUES
                    (:user_id, :username, :scout_name, :level, :xp, :wins, :losses, :kills, :coins, :active_titan)
                ON CONFLICT(user_id) DO UPDATE SET
                    username     = excluded.username,
                    scout_name   = excluded.scout_name,
                    level        = excluded.level,
                    xp           = excluded.xp,
                    wins         = excluded.wins,
                    losses       = excluded.losses,
                    kills        = excluded.kills,
                    coins        = excluded.coins,
                    active_titan = excluded.active_titan
                """,
                player_data
            )
            # sync titan collection
            uid = player_data["user_id"]
            for titan, count in collection.items():
                conn.execute(
                    "INSERT INTO player_titans (user_id, titan_name, count) VALUES (?, ?, ?)"
                    "  ON CONFLICT(user_id, titan_name) DO UPDATE SET count = excluded.count",
                    (uid, titan, count)
                )
            conn.commit()
        player_data["collection"] = collection  # restore
        await cls._run(_q, cls._conn)

    @classmethod
    async def all_players(cls) -> list[dict]:
        """Return all player rows with their titan collections."""
        def _q(conn):
            rows = conn.execute("SELECT * FROM players").fetchall()
            result = []
            for row in rows:
                titans = conn.execute(
                    "SELECT titan_name, count FROM player_titans WHERE user_id = ?",
                    (row["user_id"],)
                ).fetchall()
                d = dict(row)
                d["collection"] = {t["titan_name"]: t["count"] for t in titans}
                result.append(d)
            return result
        return await cls._run(_q, cls._conn)
