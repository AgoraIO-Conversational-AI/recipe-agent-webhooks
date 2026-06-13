# Agora Agent Backend — Webhooks Recipe

FastAPI service that owns Agora token generation, agent session lifecycle, and a
self-contained Agora NCS webhook receiver for the webhooks recipe. It is the
service the web client reaches through the Next.js `/api/*` rewrite proxy
(port 8000).

## What this service does

Starts a conversational AI agent using only Agora-managed vendors — **zero
provider-key** — and attaches correlation labels so server-side notifications can
be tied back to the session that produced them:

- `.with_labels({"recipe": "webhooks", "session": <sessionId or name>})`

It also receives Agora Notification Center Service (NCS) callbacks at
`POST /ncsNotify`, verifies the HMAC-SHA256 signature when a secret is set,
stores events append-only in SQLite, and streams them to the web over SSE.

**Pipeline:** `DeepgramSTT(nova-3, en)` → `OpenAI` (Agora-managed, keyless) → `MiniMaxTTS`

The `OpenAI` vendor is Agora-managed (keyless by default). There is **no
separate `llm/` service** in this recipe.

## The receiver — `src/webhooks.py`

- `store_event` / `recent_events` / `reset_events` — append-only SQLite store
  (`WEBHOOKS_DB_PATH`, default `/tmp/webhooks.db`; `recent_events` oldest-first).
- `verify_signature(secret, raw_body, signature_v2)` — accept if no secret is set
  (dev mode); otherwise require a matching `Agora-Signature-V2` HMAC-SHA256.
- `parse_event` / `event_display_name` — normalize the NCS envelope; `101`/`102`
  → "Agent started"/"Agent stopped".
- `SseHub` — in-process fan-out to connected SSE clients.
- `router` — `POST /ncsNotify`, `GET /webhooks/stream`, `POST /webhooks/reset`,
  mounted via `app.include_router(webhooks.router)`.

## Run

Use the repo-root `README.md` for the full local flow (`bun run dev`) and the
Console / ngrok setup. To work on this module directly:

```bash
cd server
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest
python src/server.py
```

Tests:

```bash
python -m py_compile src/*.py
pytest tests
```

## Environment

Required:

- `AGORA_APP_ID` — Agora project App ID.
- `AGORA_APP_CERTIFICATE` — Agora project App Certificate.

Optional:

| Variable | Default | Notes |
| --- | :---: | --- |
| `AGORA_NOTIFICATION_SECRET` | — | Agora-side NCS secret (Console → Notifications). Enables signature verification. **Not** an LLM/provider key. |
| `WEBHOOKS_DB_PATH` | `/tmp/webhooks.db` | Where received events are stored (ephemeral by default). |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `OPENAI_API_KEY` | — | BYO only — Agora manages the OpenAI key by default (keyless). Set only if your account requires it. |
| `AGENT_GREETING` | built-in | Optional opening line override |

## API

- `GET /get_config` — token + channel/UID config
- `POST /startAgent` — start an agent session (optional `sessionId` label)
- `POST /stopAgent` — stop an agent session
- `POST /ncsNotify` — receive an Agora NCS notification callback
- `GET /webhooks/stream` — SSE: replay recent events, then stream new ones
- `POST /webhooks/reset` — clear the stored events

The repo-root `bun run verify:local:fastapi` exercises the agent routes through
the Next proxy using a fake agent, so no live Agora session is required. To
receive real callbacks, tunnel the backend (`ngrok http 8000`) and register
`https://<ngrok>/ncsNotify` in the Agora Console → Notifications.
