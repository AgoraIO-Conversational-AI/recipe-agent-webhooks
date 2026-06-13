# Agent Development Guide

For coding agents working in `recipe-agent-webhooks`. This repository is the
**webhooks** recipe in the Agora Conversational AI recipes family.

## System shape

- **`server/`** — Python FastAPI agent backend (:8000). Owns Agora token
  generation, agent session lifecycle, and a self-contained NCS webhook receiver
  (`server/src/webhooks.py`). Uses the managed `OpenAI` vendor (Agora-managed,
  keyless) with a simple system prompt plus `with_labels`. SDK:
  `agora-agents>=2.0.0` (`import agora_agent`).
- **`web/`** — Next.js 16 / React 19 / TypeScript frontend (:3000). The
  net-new work is here: a Server-Sent-Events subscription and the webhook
  `EventTimeline`.
- Auth: Token007 from `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`; NCS callbacks
  verified via HMAC-SHA256 when `AGORA_NOTIFICATION_SECRET` is set.
- No `llm/` service — OpenAI is Agora-managed (zero provider-key by default).

## Pipeline

`DeepgramSTT(nova-3, en)` → `OpenAI` (Agora-managed, keyless) → `MiniMaxTTS`,
plus `.with_labels({"recipe": "webhooks", "session": ...})` for correlation.

## The receiver (`server/src/webhooks.py`)

A single module mounted with `app.include_router(webhooks.router)`:
- `store_event` / `recent_events` / `reset_events` — append-only SQLite store
  (`WEBHOOKS_DB_PATH`, default `/tmp/webhooks.db`; `recent_events` is oldest-first).
- `verify_signature(secret, raw_body, signature_v2)` — accept if no secret is set
  (dev mode); otherwise require a matching `Agora-Signature-V2` HMAC-SHA256.
- `parse_event` / `event_display_name` — normalize the NCS envelope; `101`/`102`
  → "Agent started"/"Agent stopped".
- `SseHub` — in-process fan-out to SSE clients.
- `router` — `POST /ncsNotify`, `GET /webhooks/stream`, `POST /webhooks/reset`.

## Routing / ownership

- UI, the SSE subscription, and the webhook `EventTimeline` live in `web/`.
- Browser-facing `/api/*` paths are Next rewrites (`web/next.config.ts`) to the
  agent backend; do not add `web/app/api/**/route.ts` for agent/token logic.
- Token generation, agent lifecycle, and the NCS receiver live in `server/src/`.
- `WebhookEvent` and the SSE helpers (`subscribeWebhooks`, `resetWebhooks`,
  `webhookEventName`) are exported from `web/src/services/api.ts`.

## Supported modes

- **Local:** `bun run dev` starts `server` (:8000) and `web` (:3000).
  The web app calls `/api/*`; Next rewrites to
  `AGENT_BACKEND_URL=http://localhost:8000`. To receive real callbacks, tunnel
  the backend (`ngrok http 8000`) and register `https://<ngrok>/ncsNotify` in the
  Agora Console → Notifications.
- **Deploy:** deploy `web` (Next) + `server` (reachable FastAPI).
  Set `AGENT_BACKEND_URL` in the web deployment; register `/ncsNotify` in Console.

## Env vars

| Variable | Default | Notes |
|---|---|---|
| `AGORA_APP_ID` | — | required |
| `AGORA_APP_CERTIFICATE` | — | required |
| `AGORA_NOTIFICATION_SECRET` | — | optional — Agora-side NCS secret; enables signature verification. NOT an LLM key |
| `WEBHOOKS_DB_PATH` | `/tmp/webhooks.db` | optional — ephemeral SQLite store path |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `OPENAI_API_KEY` | — | optional — BYO only if your account requires it |

## Patterns

- Keep the web client calling `/api/*`; hide backend placement behind Next rewrites.
- Keep token generation, the App Certificate, and the NCS secret in `server/`.
- `OPENAI_API_KEY` is optional: Agora manages the OpenAI key by default (keyless).
- This is a cascading managed-OpenAI agent (STT → LLM → TTS) plus `with_labels`.
- The receiver verifies-if-secret-set; never require a secret to run locally.

## Anti-patterns

- Do not reintroduce `llm/` or the `CustomLLM` vendor.
- Do not reintroduce Next Route Handlers for agent/token logic.
- Do not use `with_mllm` / realtime patterns — this recipe is cascading + labels.
- Do not commit `**/.env.local` or `*.db`; `server/.env.local` is a symlink to the
  shared creds and must stay gitignored.
- Do not put `PORT` in `server/.env.example` (it would clobber the random port
  that `verify:local:fastapi` injects via `load_dotenv(override=True)`).

## Commands

```bash
bun run setup
bun run dev
bun run doctor
bun run doctor:local
bun run verify         # web-only, no creds
bun run verify:local   # full local gate
```

Narrower checks: `bun run verify:backend`, `bun run verify:local:fastapi`,
`bun run verify:web:proxy`. Backend unit tests: `pytest` in `server/`.

## Done criteria

1. Run the narrowest relevant verification command.
2. Web-affecting changes: `bun run verify` passes.
3. Backend-affecting changes: `python -m py_compile src/*.py` + `pytest tests`
   pass in `server/`.
4. If you change required env vars or setup steps, update the root README,
   the relevant module README, and `server/.env.example` together.

## Git conventions

- Conventional Commits: `type: description` or `type(scope): description`
  (`feat`, `fix`, `chore`, `test`, `docs`). Lowercase after the prefix, present
  tense.
- No AI tool names in commit messages or PR descriptions. No `Co-Authored-By`
  trailers. No `--no-verify`. No git config changes.
- Branch names: `type/short-description` (e.g. `feat/add-event-filter`).
