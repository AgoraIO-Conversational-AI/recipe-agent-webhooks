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


def verify_signature(secret: Optional[str], raw_body: bytes,
                     signature_v2: Optional[str]) -> bool:
    """Accept if no secret is configured (dev mode); otherwise require a matching
    Agora-Signature-V2 (HMAC-SHA256 over the raw body)."""
    if not secret:
        return True
    if not signature_v2:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_v2)


def parse_event(body: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the NCS envelope; retain the full raw payload verbatim."""
    return {
        "eventType": body.get("eventType"),
        "notifyMs": body.get("notifyMs"),
        "sid": body.get("sid"),
        "payload": body.get("payload") or {},
    }


_EVENT_NAMES = {101: "Agent started", 102: "Agent stopped"}


def event_display_name(event_type: Optional[int]) -> str:
    if event_type in _EVENT_NAMES:
        return _EVENT_NAMES[event_type]
    if event_type is None:
        return "Event"
    return f"Event {event_type}"


from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse


class SseHub:
    """In-process fan-out of received events to connected SSE clients."""

    def __init__(self) -> None:
        self._subscribers: Set["asyncio.Queue[Dict[str, Any]]"] = set()

    def subscribe(self) -> "asyncio.Queue[Dict[str, Any]]":
        q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q) -> None:
        self._subscribers.discard(q)

    def publish(self, event: Dict[str, Any]) -> None:
        for q in list(self._subscribers):
            q.put_nowait(event)


hub = SseHub()
router = APIRouter()


@router.post("/ncsNotify")
async def ncs_notify(request: Request):
    """Receive an Agora NCS notification callback."""
    raw = await request.body()
    secret = os.getenv("AGORA_NOTIFICATION_SECRET")
    signature = request.headers.get("Agora-Signature-V2")
    if not verify_signature(secret, raw, signature):
        return Response(
            content=json.dumps({"code": 1, "msg": "invalid signature"}),
            media_type="application/json", status_code=401,
        )
    if not secret:
        logger.warning("dev mode: webhook signature unverified")
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        body = {}
    record = store_event(parse_event(body))
    hub.publish(record)
    return {"code": 0, "msg": "success"}


@router.get("/webhooks/stream")
async def webhooks_stream(request: Request):
    """SSE: replay recent events, then stream new ones live."""

    async def gen():
        for rec in recent_events():
            yield f"data: {json.dumps(rec)}\n\n"
        q = hub.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    rec = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(rec)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            hub.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/webhooks/reset")
async def webhooks_reset():
    reset_events()
    return {"code": 0, "msg": "cleared"}
