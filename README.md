# Agora Conversational AI — Webhooks Recipe (Python)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Bun](https://img.shields.io/badge/bun-latest-black)](https://bun.sh/)

The **webhooks** recipe in the Agora Conversational AI recipes family.
A **server-side notification observability** demo: the backend receives Agora
Notification Center Service (NCS) callbacks at `POST /ncsNotify`, verifies the
HMAC-SHA256 signature when a secret is configured, stores each event append-only
in SQLite, and streams them to a live web timeline over **Server-Sent Events**.
The agent attaches a `session` label so each callback can be correlated back to
the browser tab that started it — your own session's rows are highlighted.

Fully **zero provider-key** — OpenAI is Agora-managed (no `OPENAI_API_KEY`
required unless you bring your own account). The optional
`AGORA_NOTIFICATION_SECRET` is an **Agora-side** NCS secret, not an LLM key.

**Pipeline:** `DeepgramSTT(nova-3, en)` → `OpenAI` (managed, keyless) → `MiniMaxTTS`
plus `.with_labels({"recipe": "webhooks", "session": ...})`.

**Receiver endpoints (backend):**
- `POST /ncsNotify` — Agora NCS callback target (verify-if-secret-set, then store + fan-out).
- `GET /webhooks/stream` — SSE: replays recent events, then streams new ones live.
- `POST /webhooks/reset` — clears the stored events.

**Webhook event types surfaced:**
- `101` — Agent started (joined)
- `102` — Agent stopped (left; includes a leave reason where Agora provides one)

> **Note:** received NCS payloads can contain transcript or error data. The
> SQLite store defaults to an ephemeral `/tmp/webhooks.db`, is gitignored, and a
> **Clear** button (`POST /webhooks/reset`) wipes it. This recipe is **zero
> provider-key**; the NCS secret is an Agora-side secret used only to verify the
> callback signature.

## Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Bun](https://bun.sh/)
- [Agora CLI](https://github.com/AgoraIO/cli) — makes generating an App ID + App Certificate easy
- [ngrok](https://ngrok.com/) (or any tunnel) — to expose the backend so Agora Console can reach `/ncsNotify`

## Run It

```bash
# 1. Install web deps + create the Python venv
bun run setup

# 2. Add Agora credentials (CLI), or edit server/.env.local by hand
agora login
agora project use <your-project>          # select which project to use
agora project env write server/.env.local # writes App ID + Certificate

# 3. Run backend + web
bun run dev
```

Open [http://localhost:3000](http://localhost:3000). The **Server-side webhook
events** timeline is visible immediately and updates over SSE.

## Setup: receive Agora NCS callbacks

Webhook events come from Agora's cloud, so the backend must be reachable from the
internet and registered in the Console.

1. **Run the stack and expose the backend.** With `bun run dev` running, tunnel
   the backend port:

   ```bash
   ngrok http 8000
   ```

   Note the public URL ngrok prints, e.g. `https://<ngrok>.ngrok-free.app`.

2. **Register the webhook in Agora Console.** Go to your project →
   **Notifications** → enable the **Conversational AI** events (Business ID 17),
   at minimum **agent joined `101`** and **agent left `102`**. Set the webhook
   (receiver) URL to:

   ```
   https://<ngrok>/ncsNotify
   ```

3. **(Recommended) Enable signature verification.** Copy the Console
   **secret** into `AGORA_NOTIFICATION_SECRET` in `server/.env.local`. With it
   set, the receiver requires a matching `Agora-Signature-V2` HMAC-SHA256 header
   and rejects mismatches with `401`. Without it, the receiver runs in **dev
   mode** and logs `dev mode: webhook signature unverified`.

4. **Try it.** Start an agent in the web UI, then stop it. Within a few seconds
   `101` (Agent started) then `102` (Agent stopped) appear in the timeline; rows
   from your own browser session are highlighted. Use **Clear** to wipe the store.

### Working from a clone

`bun run setup` creates the Python venv and installs web dependencies.
`bun run dev` brings up both services. You still need Agora credentials in
`server/.env.local` before an agent can start, and a Console-registered
`/ncsNotify` URL before webhooks arrive.

Services:

- Frontend — http://localhost:3000
- Backend — http://localhost:8000
- API docs — http://localhost:8000/docs

## Deploy

Deploy `web` (Next.js) and `server` (a reachable FastAPI backend). Set
`AGENT_BACKEND_URL` in the web deployment so the Next rewrites reach the backend,
and register `https://<your-backend>/ncsNotify` in the Agora Console.

A backend-only Docker image exposes **BACKEND-ONLY** (:8000) and defaults
`WEBHOOKS_DB_PATH=/tmp/webhooks.db` (ephemeral). No separate LLM container is
needed — OpenAI is Agora-managed.

## Environment variables

| Variable | Required | Default | Notes |
| --- | :---: | :---: | --- |
| `AGORA_APP_ID` | ✅ | — | Agora Console → Project → App ID |
| `AGORA_APP_CERTIFICATE` | ✅ | — | Agora Console → Project → App Certificate |
| `AGORA_NOTIFICATION_SECRET` | | — | Optional. NCS secret from Agora Console → Notifications. Enables HMAC-SHA256 signature verification. **Not** an LLM/provider key. |
| `WEBHOOKS_DB_PATH` | | `/tmp/webhooks.db` | Where received events are stored (ephemeral by default). |
| `OPENAI_API_KEY` | | — | Optional — Agora manages the OpenAI key by default (keyless). Set only if your account requires it. |
| `OPENAI_MODEL` | | `gpt-4o-mini` | OpenAI model |
| `AGENT_GREETING` | | built-in | Optional opening line override |

## Commands

```bash
bun run setup            # install web deps + create server/ venv
bun run dev              # run backend (:8000) + web (:3000)

bun run doctor           # prerequisite check (no creds needed)
bun run doctor:local     # + .env.local + credentials checks

bun run verify           # web-only gate (no Agora creds needed)
bun run verify:local     # full local gate: backend compile + smoke tests + web build
bun run clean            # remove venvs and build artifacts
```

Tests run standalone (no Agora cloud needed): `pytest` in `server/`, plus
`bun run verify` in `web/`.

## Architecture

```
Agora ConvoAI Cloud
  │  agent joined / left  ──NCS callback──▶  POST /ncsNotify  (server/, :8000)
  │  (with session label)                       │  verify-if-secret-set (HMAC-SHA256)
  │                                             │  store append-only (SQLite)
  │                                             │  fan-out to SSE subscribers
  ▼                                             ▼
Browser (localhost:3000)  ◀──SSE──  GET /webhooks/stream
  │  fetch /api/get_config, /api/startAgent (sessionId), /api/stopAgent
  ▼
Next.js  ──rewrite──▶  Agent backend  (starts agent with managed OpenAI + with_labels)
```

The agent is a cascading managed-OpenAI pipeline (STT → LLM → TTS) plus
`with_labels`. No separate `llm/` service. See [ARCHITECTURE.md](./ARCHITECTURE.md).

## What You Get

- A **Next.js** web client (:3000) that subscribes to `/api/webhooks/stream` via
  `EventSource` and renders a live **Server-side webhook events** timeline.
  Rows whose `payload.labels.session` matches this tab's session are highlighted;
  a **Clear** button wipes the store.
- A **FastAPI** agent backend (:8000) that owns Agora token generation, the agent
  session lifecycle, and a self-contained NCS receiver (`server/src/webhooks.py`):
  signature verification, an append-only SQLite store, an in-process SSE hub, and
  the `/ncsNotify` / `/webhooks/stream` / `/webhooks/reset` router.
- **Managed keyless OpenAI** — Agora-managed, no `OPENAI_API_KEY` required.
- **Zero provider-key** setup — the full pipeline runs with no LLM API key by default.

## How It Works

1. The browser generates a per-tab `sessionId` and calls `/api/get_config`; the
   backend mints an Agora token.
2. The browser calls `/api/startAgent` with the `sessionId`; the backend starts
   the agent and attaches `.with_labels({"recipe": "webhooks", "session": sessionId})`.
3. Agora's cloud emits NCS notifications (agent joined `101`, agent left `102`)
   to the Console-registered `/ncsNotify` URL, carrying the labels in the payload.
4. The receiver verifies the signature (if a secret is set), stores the event
   append-only, and publishes it to the in-process SSE hub.
5. The web client's `EventSource('/api/webhooks/stream')` receives each event and
   appends it to the timeline; rows matching this tab's `sessionId` are highlighted.
6. `/api/stopAgent` ends the session (producing a `102`); **Clear** /
   `POST /webhooks/reset` empties the store.

## Repo Map

- `web/` — Next.js frontend (:3000); SSE subscription + webhook timeline.
- `server/` — FastAPI agent backend (:8000); Agora tokens, agent lifecycle, and
  the `webhooks.py` NCS receiver.
- `ARCHITECTURE.md` — system shape and component boundaries.
- `AGENTS.md` — guide for coding agents working in this repo.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| No events appear in the timeline | Confirm the Console **Notifications** webhook URL points at your public `/ncsNotify`, the `101`/`102` events are enabled, and the tunnel (ngrok) is running. |
| Receiver returns `401` | The configured `AGORA_NOTIFICATION_SECRET` does not match the Console secret, or the `Agora-Signature-V2` header is missing. Re-copy the secret or unset it to run in dev mode. |
| Local calls fail under a global proxy (Clash, etc.) | Configure your proxy to send `127.0.0.1`, `localhost`, and RFC-1918 ranges DIRECT. |

## More Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [AGENTS.md](./AGENTS.md)

## License

Released under the [MIT License](./LICENSE).
