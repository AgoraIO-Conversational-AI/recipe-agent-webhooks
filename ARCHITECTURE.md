# Architecture — Webhooks Recipe

Two processes. The browser talks only to Next.js `/api/*`, which rewrites to the
agent backend. The agent backend owns Agora tokens, agent lifecycle, and a
self-contained NCS webhook receiver. OpenAI is Agora-managed (keyless) — no
separate LLM service is needed.

The net-new work in this recipe is the **server-side receiver**
(`server/src/webhooks.py`) plus a web timeline driven by Server-Sent Events.
The agent attaches a `session` label so callbacks can be correlated to the tab
that started them.

## Request / callback flow

```
Browser
  │  GET  /api/get_config           → token + channel/UIDs
  │  POST /api/startAgent {sessionId}→ start agent session (labels attached)
  │  EventSource /api/webhooks/stream→ subscribe to the live timeline (SSE)
  ▼
Next.js  (rewrites /api/* → AGENT_BACKEND_URL)
  ▼
Agent backend (server/, :8000)
  │  builds session with:
  │    OpenAI(model=OPENAI_MODEL, system_messages=[friendly assistant])
  │    .with_labels({"recipe": "webhooks", "session": sessionId})
  ▼
Agora ConvoAI Cloud
  │  user speech → Deepgram STT (managed, nova-3, en)
  │  text → OpenAI (Agora-managed, keyless)
  │  reply → MiniMax TTS (managed)
  │
  │  Notification Center Service (NCS) → POST /ncsNotify on the backend:
  │    101 agent joined, 102 agent left (payload carries the labels)
  ▼
NCS receiver (server/src/webhooks.py)
  │  verify-if-secret-set (HMAC-SHA256 over the raw body)
  │  store append-only (SQLite, WEBHOOKS_DB_PATH)
  │  fan-out to in-process SSE subscribers
  ▼
GET /webhooks/stream  ──SSE──▶  Server-side webhook timeline in the web UI
```

`POST /api/stopAgent { agentId }` ends the session (producing a `102`).
`POST /api/webhooks/reset` clears the stored events.

## Why no llm/ service

This recipe uses the **managed OpenAI vendor**
(`agora_agent.agentkit.vendors.OpenAI`). Agora holds the OpenAI API key on its
cloud; the recipe is zero provider-key by default. An optional `OPENAI_API_KEY`
env var lets you bring your own account if needed.

This means:
- No `llm/` service to expose publicly.
- The only required credentials are `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`.
- The optional `AGORA_NOTIFICATION_SECRET` is an **Agora-side** NCS secret used
  only to verify callback signatures — it is **not** an LLM/provider key.

## The receiver (`server/src/webhooks.py`)

A single self-contained module, mounted via `app.include_router(webhooks.router)`:

| Piece | Responsibility |
| --- | --- |
| `store_event` / `recent_events` / `reset_events` | Append-only SQLite store (`WEBHOOKS_DB_PATH`, default `/tmp/webhooks.db`). `recent_events` returns oldest-first for the timeline. |
| `verify_signature(secret, raw_body, signature_v2)` | Accept if no secret is configured (dev mode); otherwise require a matching `Agora-Signature-V2` HMAC-SHA256 over the raw body. |
| `parse_event` / `event_display_name` | Normalize the NCS envelope (retain the raw payload verbatim); map `101`→"Agent started", `102`→"Agent stopped". |
| `SseHub` | In-process fan-out of received events to connected SSE clients. |
| `router` | `POST /ncsNotify`, `GET /webhooks/stream`, `POST /webhooks/reset`. |

## Webhook event surface

NCS callbacks arrive at `/ncsNotify`. The web client subscribes over SSE.

| Event type | Display name | What it carries |
| --- | --- | --- |
| `101` | Agent started | Channel, labels (`recipe`, `session`) |
| `102` | Agent stopped | Channel, leave reason (where provided), labels |
| other | `Event <n>` | Raw payload retained verbatim |

> **Note:** received payloads can contain transcript or error data. The SQLite
> store is ephemeral by default and gitignored; **Clear** / `/webhooks/reset`
> wipes it.

## API (agent backend, port 8000)

| Endpoint | Method | Description |
| --- | --- | --- |
| `/get_config` | GET | Token + channel/UID config |
| `/startAgent` | POST | Start the agent session (optional `sessionId` label) |
| `/stopAgent` | POST | Stop the agent by `agent_id` |
| `/ncsNotify` | POST | Receive an Agora NCS notification callback |
| `/webhooks/stream` | GET | SSE: replay recent events, then stream new ones |
| `/webhooks/reset` | POST | Clear the stored events |

The browser calls these as `/api/*`; Next rewrites them to `AGENT_BACKEND_URL`.

## Auth

- Browser → agent backend: none (local dev).
- Agent backend → Agora cloud: Token007, generated from `AGORA_APP_ID` +
  `AGORA_APP_CERTIFICATE`.
- Agora cloud → agent backend (NCS): HMAC-SHA256 signature in `Agora-Signature-V2`,
  verified against `AGORA_NOTIFICATION_SECRET` when set (dev mode otherwise).
- Agora cloud → OpenAI: Agora-managed key (transparent to this recipe).
  Optionally overridden by `OPENAI_API_KEY` if provided.
