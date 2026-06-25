# Agent Development Guide

For coding agents working in `recipe-agent-webhooks`. This repository is the
**webhooks** recipe in the Agora Conversational AI recipes family.

## How to Load

This repository uses progressive disclosure documentation. Docs live under
`docs/ai/` in three levels.

1. Read [docs/ai/L0_repo_card.md](docs/ai/L0_repo_card.md) to identify the repo.
2. This repo declares `Recipe Role: base`; read [docs/ai/RECIPE.md](docs/ai/RECIPE.md) before changing reusable recipe contracts.
3. Load ALL 8 files in [docs/ai/L1/](docs/ai/L1/). They are small — load all upfront.
4. Follow L2 deep-dive links only when L1 isn't detailed enough. The index is at [docs/ai/L1/L2/_index.md](docs/ai/L1/L2/_index.md).

The sections below remain the canonical contributor handbook for hands-on work;
the `docs/ai/` tree is the structured summary used by AI agents.

## System shape

- **`server/`** — Python FastAPI agent backend (:8000). Owns Agora token
  generation, agent session lifecycle, and a self-contained NCS webhook receiver
  (`server/src/webhooks.py`). Uses the managed `OpenAI` vendor (Agora-managed,
  keyless) with a simple system prompt plus `with_labels`. SDK:
  `agora-agents>=2.3.0` (`import agora_agent`).
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
5. If the change touches workflows, interfaces, gotchas, or security details,
   update the matching file under [docs/ai/L1/](docs/ai/L1/) and bump
   `Last Reviewed` in [docs/ai/L0_repo_card.md](docs/ai/L0_repo_card.md).

## Git Conventions

### Commit messages — conventional commits

- **Format:** `type: description` or `type(scope): description`
- **Types:** `feat:` (new feature), `fix:` (bug fix), `chore:` (maintenance, version bumps), `test:` (test additions/changes), `docs:` (documentation)
- **Scoped variant:** `feat(scope):`, `fix(scope):` — e.g. `fix(server): fix signature verification`
- **Lowercase after prefix** — `feat: add feature`, not `feat: Add feature`
- **Present tense** — "add feature", not "added feature"

### Branch names

- **Format:** `type/short-description` — lowercase, hyphen-separated
- **Types match commit types:** `feat/`, `fix/`, `chore/`, `test/`, `docs/`
- **Examples:** `feat/add-event-filter`, `fix/signature-hmac`, `docs/progressive-disclosure`

### General rules

- **Repo-local `AGENTS.md` is the authoritative source for repo conventions.**
- **No AI tool names** — never mention claude, cursor, copilot, cody, aider, gemini, codex, chatgpt, or gpt-3/4 in commit messages or PR descriptions.
- **No Co-Authored-By trailers** — omit AI attribution lines.
- **No `--no-verify`** — let git hooks run normally.
- **No git config changes** — do not modify `user.name` or `user.email`.

## Doc Commands

| Command       | When to use                                                                  |
| ------------- | ---------------------------------------------------------------------------- |
| generate docs | No `docs/ai/` directory exists yet                                           |
| update docs   | Code changed since the `Last Reviewed` date in L0                            |
| test docs     | Verify docs give agents the right context (writes `docs/ai/test-results.md`) |
| fix docs      | Close findings from a docs review or test run                                |

See the [progressive disclosure standard](https://github.com/AgoraIO-Community/ai-devkit/blob/main/docs/standard/progressive-disclosure-standard.md) and [workflows](https://github.com/AgoraIO-Community/ai-devkit/blob/main/docs/workflows/progressive-disclosure-docs.md) for the full specification.
