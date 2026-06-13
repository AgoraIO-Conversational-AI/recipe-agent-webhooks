# Agora Conversational AI — Events Recipe (Python)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Bun](https://img.shields.io/badge/bun-latest-black)](https://bun.sh/)

The **events** recipe in the Agora Conversational AI recipes family.
A web-centric observability demo: talk to a friendly voice assistant and watch
the agent's built-in event surface — state changes, per-stage metrics, errors,
and transcript turns — rendered in a live **EventTimeline** alongside an annotated
transcript panel. Fully **zero-key** — OpenAI is Agora-managed
(no `OPENAI_API_KEY` required unless you bring your own account).

**Pipeline:** `DeepgramSTT(nova-3, en)` → `OpenAI` (managed, keyless) → `MiniMaxTTS`

**Event surface (RTM):**
- `AGENT_STATE_CHANGED` — listening / thinking / speaking / idle
- `AGENT_METRICS` — per-stage latency (STT, LLM, TTS)
- `AGENT_ERROR` / `MESSAGE_ERROR` — error codes and messages
- `TRANSCRIPT_UPDATED` — completed voice turns

> **Limitation:** only the built-in event types listed above are available.
> There is no server-side custom-event API in this recipe.

## Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Bun](https://bun.sh/)
- [Agora CLI](https://github.com/AgoraIO/cli) — makes generating an App ID + App Certificate easy

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

Open [http://localhost:3000](http://localhost:3000) → **Start Conversation** → speak.
Watch the **Event Timeline** panel update in real time.

### Working from a clone

`bun run setup` creates the Python venv and installs web dependencies.
`bun run dev` brings up both services. You still need Agora credentials in
`server/.env.local` before a conversation can connect.

Services:

- Frontend — http://localhost:3000
- Backend — http://localhost:8000
- API docs — http://localhost:8000/docs

## Deploy

Deploy `web` (Next.js) and `server` (a reachable FastAPI backend). Set
`AGENT_BACKEND_URL` in the web deployment so the Next rewrites reach the backend.

A backend-only Docker image is published to
`ghcr.io/AgoraIO-Conversational-AI/recipe-agent-events` on `v*` tags.
It exposes **BACKEND-ONLY** (:8000). No separate LLM container is needed —
OpenAI is Agora-managed.

## Environment variables

| Variable | Required | Default | Notes |
| --- | :---: | :---: | --- |
| `AGORA_APP_ID` | ✅ | — | Agora Console → Project → App ID |
| `AGORA_APP_CERTIFICATE` | ✅ | — | Agora Console → Project → App Certificate |
| `OPENAI_MODEL` | | `gpt-4o-mini` | OpenAI model |
| `OPENAI_API_KEY` | | — | Optional — Agora manages the OpenAI key by default (keyless). Set only if your account requires it. |
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
`bun run verify` in `web/`. CI runs them on Linux/macOS/Windows × Python 3.10 & 3.13.

## Architecture

```
Browser (localhost:3000)
  │  fetch /api/*
  ▼
Next.js  ──rewrite──▶  Agent backend  (server/, localhost:8000)
                          │  starts agent session (managed OpenAI vendor)
                          │  flags: enable_rtm=true, enable_metrics=true,
                          │         enable_error_message=true
                          ▼
                       Agora ConvoAI Cloud
                          │  Deepgram STT (managed, en)
                          │  OpenAI (Agora-managed, keyless, gpt-4o-mini)
                          │  MiniMax TTS (managed)
                          │  RTM events → browser
                          ▼
                       EventTimeline + annotated transcript in the web UI
```

No separate `llm/` service. See [ARCHITECTURE.md](./ARCHITECTURE.md).

## What You Get

- A **Next.js** web client (:3000) with a live **EventTimeline** (state, metric,
  error, turn events; reverse-chronological, capped at 50) and an **annotated
  transcript** that shows the current agent state in the header.
- A **FastAPI** agent backend (:8000) that owns Agora token generation and the
  agent session lifecycle. The backend has no special event logic — it simply
  enables the built-in flags (`enable_rtm`, `enable_metrics`, `enable_error_message`).
- **Managed keyless OpenAI** — Agora-managed, no `OPENAI_API_KEY` required.
- **Zero-key** setup — the full pipeline runs with no LLM API key by default.

## How It Works

1. The browser calls `/api/get_config`; the backend mints an Agora token.
2. The browser joins the RTC channel, then calls `/api/startAgent`; the backend
   starts the agent with `data_channel="rtm"`, `enable_metrics=True`, and
   `enable_error_message=True`.
3. The agent speaks with the user. Agora emits RTM events for every state change,
   per-stage metric, transcript turn, and error.
4. The web client's `AgoraVoiceAI` SDK receives these events and appends a
   `TimelineEvent` for each one (capped at 50).
5. `EventTimeline` renders the events in reverse-chronological order with a
   colored badge per kind. The transcript header shows the current agent state.
6. `/api/stopAgent` ends the session.

## Repo Map

- `web/` — Next.js frontend (:3000); RTC/RTM lifecycle, EventTimeline, transcript.
- `server/` — FastAPI agent backend (:8000); Agora tokens + agent lifecycle.
- `ARCHITECTURE.md` — system shape and component boundaries.
- `AGENTS.md` — guide for coding agents working in this repo.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| No events appear in the timeline | Ensure `enable_rtm`, `enable_metrics`, `enable_error_message` are set (they are, by default in this recipe). |
| Local calls fail under a global proxy (Clash, etc.) | Configure your proxy to send `127.0.0.1`, `localhost`, and RFC-1918 ranges DIRECT. |

## More Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [AGENTS.md](./AGENTS.md)

## License

Released under the [MIT License](./LICENSE).
