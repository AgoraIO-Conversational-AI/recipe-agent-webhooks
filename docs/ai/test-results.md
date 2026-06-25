# Docs Test Results

**Reviewed:** 2026-06-25
**Branch:** `docs/progressive-disclosure`
**Repo:** `AgoraIO-Conversational-AI/recipe-agent-webhooks`

## Structural Checks

| Check | Result |
| ----- | ------ |
| `docs/ai/L0_repo_card.md` exists | PASS |
| `docs/ai/RECIPE.md` exists | PASS |
| `docs/ai/L1/` has exactly 8 files (01–08) | PASS |
| `docs/ai/L1/L2/_index.md` exists | PASS |
| `docs/ai/L1/L2/` has 2 deep dives | PASS |
| `AGENTS.md` has "## How to Load" section | PASS |
| `AGENTS.md` has "## Git Conventions" section | PASS |
| `AGENTS.md` has "## Doc Commands" section | PASS |
| `CLAUDE.md` redirects to `@AGENTS.md` | PASS |
| All relative links in `docs/ai/**/*.md` resolve | PASS (26/26) |
| All relative links in `AGENTS.md` resolve | PASS (6/6) |
| L0 Identity table has all 9 required fields | PASS |
| L0 line count ≤ 50 | PASS (47 lines) |
| RECIPE.md has YAML frontmatter | PASS |
| RECIPE.md `recipe_version` matches L0 `Recipe Version` | PASS (1.0.0) |

## Backend Test Suite

Venv: `/tmp/v_webhooks` (Python 3.14.4, pytest 9.1.1)
Install: `pip install -r requirements.txt -r requirements-dev.txt`

```
15 passed, 1 warning in 0.69s
```

| Test | Result |
| ---- | ------ |
| `test_agent_config.py::test_agent_constructs` | PASS |
| `test_agent_config.py::test_webhooks_routes_are_mounted` | PASS |
| `test_agent_construction.py::test_start_constructs_real_agent_and_returns_shape` | PASS |
| `test_webhooks.py::test_store_and_recent_roundtrip` | PASS |
| `test_webhooks.py::test_recent_is_newest_last_and_append_only` | PASS |
| `test_webhooks.py::test_reset_clears` | PASS |
| `test_webhooks.py::test_verify_dev_mode_when_secret_unset` | PASS |
| `test_webhooks.py::test_verify_requires_matching_hmac_when_secret_set` | PASS |
| `test_webhooks.py::test_parse_event_extracts_envelope` | PASS |
| `test_webhooks.py::test_parse_event_tolerates_missing_fields` | PASS |
| `test_webhooks.py::test_event_display_name` | PASS |
| `test_webhooks.py::test_ncsnotify_stores_and_returns_200_dev_mode` | PASS |
| `test_webhooks.py::test_ncsnotify_rejects_bad_signature_when_secret_set` | PASS |
| `test_webhooks.py::test_reset_endpoint` | PASS |
| `test_webhooks.py::test_sse_hub_publish_subscribe` | PASS |

Warning: `StarletteDeprecationWarning` (httpx vs httpx2) — upstream dependency, not a doc issue.

Venv cleaned: `rm -rf /tmp/v_webhooks`

## Q&A Verification (≥12 across 5 categories)

Each answer was verified against the source files listed.

### Category 1: Setup & Prerequisites

**Q1.** What are the required env vars to boot the server?
**A:** `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE`. Source: `server/src/agent.py` line 47 (`raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE are required")`).
**Result:** PASS — L1/01_setup.md and L1/06_interfaces.md both list these as the only required variables.

**Q2.** Is `OPENAI_API_KEY` required?
**A:** No. It is optional; the `OpenAI` vendor is Agora-managed by default. Source: `server/src/agent.py` line 43 (`self.openai_api_key = os.getenv("OPENAI_API_KEY")`), passed as `api_key=self.openai_api_key` (may be `None`).
**Result:** PASS — L1/01_setup.md and L0_repo_card.md correctly state "zero provider-key".

**Q3.** What does `bun run verify` run?
**A:** `bun run verify:web` → `doctor` + `verify:web:api` (contract checks) + `verify:web:build`. Source: root `package.json` `"verify": "bun run verify:web"` and `"verify:web"` script.
**Result:** PASS — L1/01_setup.md and L1/05_workflows.md accurately describe this.

### Category 2: Architecture & Topology

**Q4.** What is the full backend route list?
**A:** `GET /get_config`, `POST /startAgent`, `POST /stopAgent` (from `server.py` router) + `POST /ncsNotify`, `GET /webhooks/stream`, `POST /webhooks/reset` (from `webhooks.router`). Source: `server/src/server.py` and `server/src/webhooks.py`.
**Result:** PASS — L1/06_interfaces.md lists all 6 routes.

**Q5.** How does the browser's webhook timeline stay live?
**A:** `LandingPage.tsx` opens an `EventSource('/api/webhooks/stream')` via `subscribeWebhooks`. On connect, the server replays `recent_events()` (oldest-first), then streams new events as they arrive from `SseHub`. Source: `web/src/services/api.ts`, `server/src/webhooks.py` `webhooks_stream`.
**Result:** PASS — L1/02_architecture.md and L1/06_interfaces.md describe the SSE replay + stream flow accurately.

**Q6.** Why is there no `llm/` service?
**A:** The recipe uses the managed `OpenAI` vendor (`agora_agent.agentkit.vendors.OpenAI`); Agora holds the OpenAI key on its cloud. Source: `server/src/agent.py` imports and `ARCHITECTURE.md` "Why no llm/ service" section.
**Result:** PASS — L1/02_architecture.md explains this correctly.

### Category 3: Webhook Receiver / Signature

**Q7.** What happens when `AGORA_NOTIFICATION_SECRET` is not set?
**A:** `verify_signature` returns `True` (dev mode). The receiver logs `"dev mode: webhook signature unverified"` and stores the event. Source: `server/src/webhooks.py` lines 97–99, 165–167.
**Result:** PASS — L1/07_gotchas.md, L1/08_security.md, and L2/webhook_receiver.md all describe this correctly.

**Q8.** What is the signature algorithm?
**A:** HMAC-SHA256 computed over the **raw request body bytes** using `hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()`, compared constant-time via `hmac.compare_digest`. Source: `server/src/webhooks.py` lines 102–103.
**Result:** PASS — L2/webhook_receiver.md documents the exact algorithm from source.

**Q9.** What does the SQLite `events` table schema look like?
**A:** `id INTEGER PRIMARY KEY AUTOINCREMENT, event_type INTEGER, notify_ms INTEGER, sid TEXT, payload TEXT, received_ms INTEGER`. Source: `server/src/webhooks.py` `_get_db()` lines 27–31.
**Result:** PASS — L2/webhook_receiver.md reproduces the schema verbatim from source.

### Category 4: Web / Browser API

**Q10.** What is the `startAgent` request body?
**A:** `{ channelName: string, rtcUid: int, userUid: int, sessionId?: string, parameters?: object }`. Source: `server/src/server.py` `StartAgentRequest` model; `web/src/services/api.ts` `startAgent`.
**Result:** PASS — L1/06_interfaces.md lists all fields including the optional `sessionId`.

**Q11.** What functions does `web/src/services/api.ts` export related to webhooks?
**A:** `subscribeWebhooks`, `resetWebhooks`, `webhookEventName`, and the `WebhookEvent` interface. Source: `web/src/services/api.ts` lines 55–80.
**Result:** PASS — L1/06_interfaces.md and L1/03_code_map.md both list these exports accurately.

**Q12.** How does the `EventTimeline` highlight rows from the current tab?
**A:** It reads `payload.labels.session` from each event and compares with `ownSession` prop. Rows where they match get the `event-row--mine` CSS class. Source: `web/src/components/EventTimeline.tsx` `sessionOf` function and `mine` variable.
**Result:** PASS — L1/02_architecture.md and L2/session_lifecycle.md describe the correlation mechanism accurately.

### Category 5: Security & Deployment

**Q13.** Is `AGORA_NOTIFICATION_SECRET` a provider/LLM key?
**A:** No. It is an Agora-side NCS secret from Agora Console → Notifications, used only to verify callback HMAC-SHA256 signatures. Source: `server/.env.example` comment, `server/src/webhooks.py`.
**Result:** PASS — L1/01_setup.md, L1/08_security.md, and L0_repo_card.md all note "NOT an LLM key".

**Q14.** What does the Docker image expose, and what is the default `WEBHOOKS_DB_PATH`?
**A:** Backend only (`:8000`); defaults `WEBHOOKS_DB_PATH=/tmp/webhooks.db` (ephemeral). Source: `README.md` Deploy section.
**Result:** PASS — L1/08_security.md deployment notes and L1/07_gotchas.md both cover this.

## Summary Table

| Category | Questions | Pass | Fail |
| -------- | --------- | ---- | ---- |
| Setup & Prerequisites | 3 | 3 | 0 |
| Architecture & Topology | 3 | 3 | 0 |
| Webhook Receiver / Signature | 3 | 3 | 0 |
| Web / Browser API | 3 | 3 | 0 |
| Security & Deployment | 2 | 2 | 0 |
| **Total** | **14** | **14** | **0** |

## Fix / Retest

No failures recorded. No fixes required.
