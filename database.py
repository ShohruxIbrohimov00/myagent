"""
SQLite ma'lumotlar bazasi (oddiy, faylga asoslangan).

Uch narsani saqlaydi:
1. seen      - allaqachon ko'rib chiqilgan manba xabarlar (takror ishlamaslik uchun)
2. published - chop etilgan postlar mavzulari (dublikatni aniqlash uchun)
3. pending   - admin tasdig'ini kutayotgan postlar

sqlite3 sinxron bo'lgani uchun har bir amal asyncio.to_thread da bajariladi.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    channel    TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    ts         INTEGER NOT NULL,
    PRIMARY KEY (channel, message_id)
);

CREATE TABLE IF NOT EXISTS published (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    topic  TEXT NOT NULL,
    title  TEXT,
    ts     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pending (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT,
    title       TEXT,
    post_text   TEXT NOT NULL,
    media_path  TEXT,
    source      TEXT,
    ts          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_sync() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


async def init() -> None:
    await asyncio.to_thread(_init_sync)


# ---------- seen (ko'rilgan xabarlar) ----------
def _is_seen_sync(channel: str, message_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen WHERE channel=? AND message_id=?",
            (channel, message_id),
        ).fetchone()
        return row is not None


def _mark_seen_sync(channel: str, message_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen (channel, message_id, ts) VALUES (?,?,?)",
            (channel, message_id, int(time.time())),
        )


async def is_seen(channel: str, message_id: int) -> bool:
    return await asyncio.to_thread(_is_seen_sync, channel, message_id)


async def mark_seen(channel: str, message_id: int) -> None:
    await asyncio.to_thread(_mark_seen_sync, channel, message_id)


# ---------- published (dedup uchun) ----------
def _recent_topics_sync(limit: int) -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT topic FROM published ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [r["topic"] for r in rows]


def _add_published_sync(topic: str, title: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO published (topic, title, ts) VALUES (?,?,?)",
            (topic, title, int(time.time())),
        )


async def recent_topics(limit: int = 30) -> list[str]:
    return await asyncio.to_thread(_recent_topics_sync, limit)


async def add_published(topic: str, title: str) -> None:
    await asyncio.to_thread(_add_published_sync, topic, title)


# ---------- pending (tasdiq kutayotganlar) ----------
def _add_pending_sync(d: dict) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO pending (topic, title, post_text, media_path, source, ts)"
            " VALUES (?,?,?,?,?,?)",
            (d.get("topic"), d.get("title"), d["post_text"],
             d.get("media_path"), d.get("source"), int(time.time())),
        )
        return cur.lastrowid


def _get_pending_sync(pid: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM pending WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None


def _del_pending_sync(pid: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM pending WHERE id=?", (pid,))


async def add_pending(data: dict) -> int:
    return await asyncio.to_thread(_add_pending_sync, data)


async def get_pending(pid: int) -> dict | None:
    return await asyncio.to_thread(_get_pending_sync, pid)


async def del_pending(pid: int) -> None:
    await asyncio.to_thread(_del_pending_sync, pid)


# ---------- settings (kalit-qiymat sozlamalar, masalan persona) ----------
def _get_setting_sync(key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def _set_setting_sync(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


async def get_setting(key: str) -> str | None:
    return await asyncio.to_thread(_get_setting_sync, key)


async def set_setting(key: str, value: str) -> None:
    await asyncio.to_thread(_set_setting_sync, key, value)
