# 03 · Code Map

> Where things live. Two top-level modules: `web/` (Next.js client) and `server/` (FastAPI backend). Orchestration is in the root `package.json`.

## Root

| Path                  | Responsibility                                                           |
| --------------------- | ------------------------------------------------------------------------ |
| `package.json`        | Bun workspace; `setup`, `dev`, `doctor*`, `verify*`, `clean` scripts.   |
| `README.md`           | Setup, run modes, env, ngrok/Console setup, troubleshooting.             |
| `ARCHITECTURE.md`     | System shape and component boundaries.                                   |
| `AGENTS.md`           | Coding-agent handbook (this file adds How to Load / Git Conventions / Doc Commands). |
| `Dockerfile`          | Backend-only image (`:8000`). Defaults `WEBHOOKS_DB_PATH=/tmp/webhooks.db`. |
| `.github/workflows/`  | `ci.yml` (backend pytest matrix + web verify), `docker.yml`, `nightly.yml`. |

## `server/` — FastAPI backend (:8000)

| Path                              | Responsibility                                                              |
| --------------------------------- | --------------------------------------------------------------------------- |
| `src/server.py`                   | FastAPI app, CORS, route handlers (`get_config`, `startAgent`, `stopAgent`), error mapping, mounts `webhooks.router`, uvicorn entrypoint. |
| `src/agent.py`                    | `Agent` class: `AsyncAgora` client, cascading pipeline build (DeepgramSTT → OpenAI → MiniMaxTTS), `.with_labels`, `start()`/`stop()`, `_sessions`. |
| `src/webhooks.py`                 | Self-contained NCS receiver: SQLite store, HMAC-SHA256 signature verification, `SseHub`, and the `router` (`/ncsNotify`, `/webhooks/stream`, `/webhooks/reset`). |
| `tests/test_webhooks.py`          | Store, signature, parse, display-name, HTTP endpoints, SSE hub unit tests. |
| `tests/test_agent_construction.py`| Builds the real `AgoraAgent`, fakes the SDK session, asserts start/stop shape. |
| `tests/test_agent_config.py`      | Smoke: `Agent` constructs, all webhooks routes are mounted on the app.      |
| `tests/conftest.py`               | `fake_env` fixture + `FakeAgent`; no cloud, no real creds.                  |
| `.env.example`                    | Env template (do not add `PORT`).                                           |
| `requirements*.txt`               | Runtime + dev (pytest) deps.                                                |

## `server/src/server.py` routes

- `GET /get_config` — token + channel/UID config.
- `POST /startAgent` — start the agent session (optional `sessionId` label).
- `POST /stopAgent` — stop by `agent_id`.
- *(from `webhooks.router`)* `POST /ncsNotify`, `GET /webhooks/stream`, `POST /webhooks/reset`.

## `web/` — Next.js client (:3000)

| Path                                      | Responsibility                                                        |
| ----------------------------------------- | --------------------------------------------------------------------- |
| `next.config.ts`                          | `/api/*` rewrites to `AGENT_BACKEND_URL`; strict mode; Turbopack root. Includes rewrites for all 6 backend paths. |
| `src/services/api.ts`                     | Browser API client: `getConfig`, `startAgent`, `stopAgent`, `subscribeWebhooks`, `resetWebhooks`, `webhookEventName`. Exports `WebhookEvent` type. |
| `src/lib/conversation.ts`                 | Transcript normalization, timestamp/UID mapping, visualizer state.    |
| `src/lib/agora.ts`                        | `DEFAULT_AGENT_UID` constant.                                         |
| `src/components/LandingPage.tsx`          | Per-tab `sessionId` generation; `subscribeWebhooks` subscription; config fetch, agent start, RTM login, teardown; renders `EventTimeline`. |
| `src/components/ConversationComponent.tsx`| RTC join, mic publish, transcript/metrics/state listeners.            |
| `src/components/EventTimeline.tsx`        | Renders the live webhook event timeline; highlights rows matching `ownSession`; **Clear** button calls `resetWebhooks`. |
| `scripts/verify-api-contracts.ts`         | Asserts all 6 rewrites + client paths + response envelope (no network). |
| `scripts/verify-local-proxy.ts`           | Stub backend; proxies `/api/*` through the rewrite map.               |
| `scripts/verify-local-fastapi.ts`         | Spawns real FastAPI with `FakeAgent`; proxies routes end-to-end.      |
| `scripts/doctor.ts`                       | Web prerequisite check.                                               |

## Related Deep Dives

- None. For runtime flow see [02_architecture](02_architecture.md); for contracts see [06_interfaces](06_interfaces.md).
