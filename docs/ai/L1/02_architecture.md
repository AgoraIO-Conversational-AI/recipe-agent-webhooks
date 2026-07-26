# 02 · Architecture

> Two co-located processes. The browser talks only to Next.js `/api/*`, which rewrites to the FastAPI agent backend. The net-new work is the NCS receiver (`server/src/webhooks.py`): HMAC-SHA256 signature verification, append-only SQLite storage, an in-process SSE hub, and a live timeline in the web client.

## Topology

```
Browser (localhost:3000)
  │  GET /api/get_config, POST /api/startAgent (sessionId), EventSource /api/webhooks/stream
  ▼
Next.js (web/)  ──rewrite──▶  Agent backend (server/, :8000)
                                 │  builds session: DeepgramSTT → OpenAI (managed) → MiniMaxTTS
                                 │  attaches .with_labels({"recipe": "webhooks", "session": sessionId})
                                 ▼
                              Agora ConvoAI Cloud
                                 │  NCS → POST /ncsNotify (backend)
                                 │    verify-if-secret-set (HMAC-SHA256)
                                 │    store append-only (SQLite)
                                 │    fan-out to SSE hub
                                 ▼
                              GET /webhooks/stream  ──SSE──▶  EventTimeline in web UI
```

- **`web/`** — Next.js 16 / React 19 / TypeScript. Owns UI, RTC/RTM client lifecycle, SSE subscription, and `EventTimeline`. Calls only `/api/*`.
- **`server/`** — Python FastAPI (:8000). Owns Agora token generation, agent session lifecycle, and the self-contained NCS receiver (`webhooks.py`). SDK: `agora-agents>=2.3.0` (`import agora_agent`).
- No `llm/` service — OpenAI is Agora-managed (zero provider-key by default).

## Request / callback lifecycle

1. Browser generates a per-tab `sessionId` (UUID) and calls `GET /api/get_config`; backend mints a Token007 from `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE` and returns channel + UIDs.
2. Browser calls `POST /api/startAgent` with `sessionId`; backend starts the agent and attaches `.with_labels({"recipe": "webhooks", "session": sessionId})`.
3. Agora's cloud emits NCS notifications (`101` agent joined, `102` agent left) to the Console-registered `/ncsNotify` URL, carrying the labels in the payload.
4. The receiver verifies the signature (if `AGORA_NOTIFICATION_SECRET` is set), stores the event append-only in SQLite, and publishes it to the in-process `SseHub`.
5. The browser's `EventSource('/api/webhooks/stream')` receives each event; the `EventTimeline` renders rows, highlighting those matching this tab's `sessionId`.
6. `POST /api/stopAgent { agentId }` ends the session (producing a `102`). `POST /api/webhooks/reset` empties the store.

## Why no `llm/` service

This recipe uses the **managed OpenAI vendor** (`agora_agent.agentkit.vendors.OpenAI`). Agora holds the OpenAI API key on its cloud. The only required credentials are `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`. The optional `AGORA_NOTIFICATION_SECRET` is an Agora-side NCS secret used only to verify callback signatures.

## Key abstractions

- **`Agent`** (`server/src/agent.py`) — async wrapper around `AgoraAgent`; owns `AsyncAgora` client, pipeline build, and the in-memory `_sessions` map keyed by `agent_id`.
- **`webhooks` module** (`server/src/webhooks.py`) — the full NCS receiver: SQLite store, signature verification, `SseHub`, and the `router` mounted via `app.include_router(webhooks.router)`.
- **`SseHub`** — in-process `asyncio.Queue`-based fan-out from `POST /ncsNotify` to connected `GET /webhooks/stream` clients. Sends keepalives every 15 s.
- **Rewrite proxy** (`web/next.config.ts`) — the only browser→backend boundary; no Next Route Handlers for agent/token logic.

## Tech decisions

- **Rewrites, not Route Handlers** — hides backend placement behind `/api/*` so the same client works locally and deployed.
- **Append-only SQLite** — `GET /webhooks/stream` replays `recent_events()` (oldest-first, newest last) on connect, then streams new events live. `POST /webhooks/reset` empties the store.
- **Verify-if-secret-set** — the receiver accepts all callbacks when `AGORA_NOTIFICATION_SECRET` is unset (dev mode), and enforces HMAC-SHA256 when it is set. This lets local development work without configuring a secret.
- **Session label correlation** — the agent attaches `{"session": sessionId}` as a label; NCS payloads carry that label back, letting the web client highlight its own rows.

## Related Deep Dives

- [webhook_receiver](L2/webhook_receiver.md) — full NCS receiver internals: signature algorithm, SQLite schema, SSE wire format, `SseHub` lifecycle.
- [session_lifecycle](L2/session_lifecycle.md) — browser orchestration of config + start/stop, per-tab sessionId, RTC/RTM, EventTimeline subscription.
