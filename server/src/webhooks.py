"""Agora NCS webhook receiver — server-side notification observability.

Receives Agora Notification Center (NCS) callbacks at POST /ncsNotify, verifies
the HMAC-SHA256 signature when a secret is configured, stores events append-only
in SQLite, and streams them to the web over SSE. Zero provider key.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("uvicorn.error")


def _db_path() -> str:
    return os.getenv("WEBHOOKS_DB_PATH", "/tmp/webhooks.db")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, event_type INTEGER, notify_ms INTEGER, "
        "sid TEXT, payload TEXT, received_ms INTEGER)"
    )
    return conn


def _row_to_record(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "eventType": row[1],
        "notifyMs": row[2],
        "sid": row[3],
        "payload": json.loads(row[4]) if row[4] else {},
        "receivedMs": row[5],
    }


def store_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Append an event; returns the stored record (with id + receivedMs)."""
    received_ms = int(time.time() * 1000)
    conn = _get_db()
    try:
        cur = conn.execute(
            "INSERT INTO events (event_type, notify_ms, sid, payload, received_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (event.get("eventType"), event.get("notifyMs"), event.get("sid"),
             json.dumps(event.get("payload") or {}), received_ms),
        )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "eventType": event.get("eventType"),
            "notifyMs": event.get("notifyMs"),
            "sid": event.get("sid"),
            "payload": event.get("payload") or {},
            "receivedMs": received_ms,
        }
    finally:
        conn.close()


def recent_events(limit: int = 100) -> List[Dict[str, Any]]:
    """Most recent events, returned oldest-first (newest last) for the timeline."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT id, event_type, notify_ms, sid, payload, received_ms "
            "FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    records = [_row_to_record(r) for r in rows]
    records.reverse()
    return records


def reset_events() -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM events")
        conn.commit()
    finally:
        conn.close()
