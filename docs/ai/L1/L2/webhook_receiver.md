**When to Read This:** Load this document when changing signature verification logic, the SQLite event store, the SSE wire format, `SseHub` lifecycle, or the `parse_event`/`event_display_name` mapping. Also read before adding new NCS event types or deploying in a multi-worker environment.

# Webhook Receiver — Deep Dive

The entire NCS receiver lives in `server/src/webhooks.py`, mounted on the FastAPI app via `app.include_router(webhooks.router)`. All pieces are in a single module so they can be unit-tested in isolation.

## HMAC-SHA256 Signature Verification

### Algorithm

```python
def verify_signature(secret: Optional[str], raw_body: bytes,
                     signature_v2: Optional[str]) -> bool:
    if not secret:
        return True          # dev mode: accept all
    if not signature_v2:
        return False         # secret set but header missing → reject
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_v2)
```

Key points:
- The digest is computed over the **raw request body** (bytes), not the decoded JSON. FastAPI's `await request.body()` provides this before any parsing.
- `hmac.compare_digest` is constant-time — safe against timing attacks.
- An empty string `""` for `secret` is treated the same as `None` (falsy) → dev mode.
- The header name is `Agora-Signature-V2` (case-sensitive in `request.headers.get(...)`).

### Flow in `/ncsNotify`

1. `raw = await request.body()` — read the raw body first.
2. `secret = os.getenv("AGORA_NOTIFICATION_SECRET")` — read at request time (supports hot-reload without restart).
3. `signature = request.headers.get("Agora-Signature-V2")`.
4. If `verify_signature` returns `False` → return 401, store nothing.
5. If `not secret` → log dev-mode warning.
6. Parse JSON from `raw`, normalize with `parse_event`, store with `store_event`, publish to `hub`.

## SQLite Store

### Schema

```sql
CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type   INTEGER,
  notify_ms    INTEGER,
  sid          TEXT,
  payload      TEXT,     -- JSON-encoded verbatim payload
  received_ms  INTEGER   -- epoch milliseconds at receipt time
)
```

- `id` is the append-only sequence; `recent_events` orders by `id DESC LIMIT 100` then reverses for oldest-first output.
- `payload` stores the full raw NCS `payload` field as a JSON string; parsed back to dict on read.
- `WEBHOOKS_DB_PATH` is read at each `_get_db()` call, so changes to the env var take effect without restart.
- Each call opens a new connection and closes it in a `finally` block — there is no persistent connection pool.

### `recent_events()` ordering

```python
rows = conn.execute(
    "SELECT ... FROM events ORDER BY id DESC LIMIT ?", (limit,)
).fetchall()
records = [_row_to_record(r) for r in rows]
records.reverse()   # oldest-first for the timeline
return records
```

The `EventSource` replay on connect replays these in order (oldest → newest), so the timeline builds up chronologically.

### `reset_events()`

`DELETE FROM events` — no `DROP TABLE`. The table remains; only rows are cleared.

## NCS Event Payload Schema

NCS payloads from Agora's Notification Center Service (Business ID 17) follow this envelope:

| Field        | Type    | Notes                                                   |
| ------------ | ------- | ------------------------------------------------------- |
| `eventType`  | integer | `101` = agent joined, `102` = agent left                |
| `notifyMs`   | integer | Millisecond timestamp from Agora when the event fired   |
| `sid`        | string  | Agora notification session ID                           |
| `payload`    | object  | Event-specific data; varies by `eventType`              |

### `eventType 101` — Agent started

`payload` typically includes:
- `channelName` — the RTC channel
- `labels` — `{"recipe": "webhooks", "session": "<sessionId>"}` as attached by `.with_labels()`

### `eventType 102` — Agent stopped

`payload` typically includes:
- `channelName`
- `leaveReason` or `reason` — why the agent left (idle timeout, explicit stop, etc.)
- `labels` — same label map as `101`

### Unknown event types

`parse_event` retains the raw payload verbatim. `event_display_name` returns `"Event <n>"` for unrecognized types. The receiver does not reject unknown types — they are stored and streamed.

### `_EVENT_NAMES` mapping

```python
_EVENT_NAMES = {101: "Agent started", 102: "Agent stopped"}
```

Both the Python backend (`event_display_name`) and the TypeScript frontend (`webhookEventName` in `api.ts`) implement the same mapping. Keep them in sync when adding new types.

## SSE Wire Format

`GET /webhooks/stream` returns `text/event-stream`. Each event is one SSE `data:` frame:

```
data: {"id":1,"eventType":101,"notifyMs":1700000000000,"sid":"abc","payload":{...},"receivedMs":1700000000123}\n\n
```

- Each `data: <json>\n\n` is a complete SSE event; `id:` and `event:` fields are not set.
- Keepalives are SSE comment lines: `: keepalive\n\n` (no `data:`) every 15 s of inactivity (`asyncio.wait_for(q.get(), timeout=15)` raises `TimeoutError`).
- The browser's `EventSource.onmessage` receives only `data:` frames; keepalives are silently ignored.

## `SseHub` Lifecycle

```python
class SseHub:
    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q) -> None:
        self._subscribers.discard(q)

    def publish(self, event: Dict[str, Any]) -> None:
        for q in list(self._subscribers):
            q.put_nowait(event)
```

- The module-level `hub = SseHub()` is shared across all requests in a single process.
- `subscribe` is called at the start of each SSE generator; `unsubscribe` is in a `finally` block to guarantee cleanup on disconnect or error.
- `publish` iterates a snapshot (`list(self._subscribers)`) to avoid mutation-during-iteration.
- `put_nowait` is used (not `await q.put()`): the queue is unbounded, so it does not block. If a slow client's queue grows unboundedly, the only mitigation is connection management (e.g., limit to 200 events on the client side, as `LandingPage.tsx` does).

## Multi-worker limitation

The `SseHub` is in-process only. In a multi-worker setup (e.g., Gunicorn), clients connected to different workers will miss events published to other workers. Replace `SseHub` with a Redis pub/sub channel or similar for multi-worker production deployments.
