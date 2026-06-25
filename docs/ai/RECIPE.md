---
recipe_version: 1.0.0
recipe_status: experimental
extension_points:
  - id: api.routes
    name: Browser-facing API routes
  - id: agent.pipeline-config
    name: Agent pipeline vendors, model, VAD, greeting, session parameters, and labels
  - id: webhooks.event-types
    name: NCS event type mapping and EventTimeline rendering
  - id: web.conversation-ui
    name: Conversation UI panels, EventTimeline, and controls
  - id: verification.contracts
    name: Contract, proxy, and local FastAPI smoke verification
invariants:
  - id: api.rewrite-boundary
    summary: Browser calls stay on /api/* and Next rewrites to FastAPI; no Route Handlers for agent/token logic.
  - id: secrets.server-only
    summary: Agora App Certificate and AGORA_NOTIFICATION_SECRET stay in the Python backend.
  - id: agent.cascade-plus-labels
    summary: A cascading managed-OpenAI pipeline (STT → LLM → TTS) with .with_labels; no with_mllm, no llm/ service.
  - id: receiver.verify-if-secret-set
    summary: NCS signature verification is optional (dev mode when unset); never require a secret to boot.
  - id: token.uid-concrete
    summary: Backend resolves missing, zero, or negative UIDs before issuing an RTC+RTM token.
stable_contracts:
  - id: env.required
    summary: AGORA_APP_ID and AGORA_APP_CERTIFICATE are required; AGENT_BACKEND_URL is required by deployed web rewrites.
  - id: api.core-routes
    summary: GET /api/get_config, POST /api/startAgent, POST /api/stopAgent, POST /api/ncsNotify, GET /api/webhooks/stream, POST /api/webhooks/reset remain the browser-facing contract.
  - id: response.envelope
    summary: Successful backend responses use { code, msg, data }; /webhooks/reset uses msg "cleared".
  - id: sse.format
    summary: GET /webhooks/stream streams data:<json>\n\n frames; keepalives are SSE comments ": keepalive\n\n".
---

# Recipe Contract

This base recipe defines the reusable surface for a Python-backed Agora Conversational AI **webhooks** quickstart: a server-side NCS receiver with signature verification, SQLite storage, and SSE-driven web timeline, combined with a cascading managed-OpenAI voice agent.

## Recipe Role

- Role: `base` recipe (self-contained, clone-and-run; no `Extends` pin).
- Target audience: developers adding server-side Agora NCS webhook observability to a Conversational AI Python backend.
- Reuse model: clone, bind project, set up ngrok + Console Notifications, run, then customize event handling or agent behavior.

## Recipe Scope

- Python FastAPI token generation and managed agent lifecycle.
- Cascading managed-OpenAI pipeline (`DeepgramSTT` → `OpenAI` → `MiniMaxTTS`) with correlation labels via `.with_labels`.
- Self-contained NCS receiver (`webhooks.py`): HMAC-SHA256 signature verification, append-only SQLite, in-process SSE fan-out.
- Next.js browser UI with RTC audio, RTM transcript/metrics, and a live `EventTimeline` driven by Server-Sent Events.
- Rewrite-only `/api/*` browser facade hiding backend placement.
- Contract, proxy, and local FastAPI smoke verification that need no live Agora calls.

## Baseline Implementation Guidance

Use this repo's source and progressive disclosure docs as the starting point, then customize. Do not recreate the NCS receiver or Agora ConvoAI integration from memory — signature verification, SQLite schema, SSE wire format, SDK builder fields, and token behavior drift. Copy verified patterns from this repo.

## Extension Points

| ID | Surface | How to extend | Required follow-up |
| -- | ------- | ------------- | ------------------ |
| `api.routes` | `server/src/server.py`, `web/next.config.ts`, `web/src/services/api.ts` | Add FastAPI route, add rewrite, add browser fetch helper. | Extend `web/scripts/verify-api-contracts.ts`; add proxy/fastapi coverage if it belongs in local verification. |
| `agent.pipeline-config` | `server/src/agent.py` | Change model, VAD, greeting, codec, or `with_labels` content. | Run `verify:backend` + `pytest tests`; document new env in `server/.env.example`. |
| `webhooks.event-types` | `server/src/webhooks.py` (`_EVENT_NAMES`), `web/src/services/api.ts` (`webhookEventName`), `web/src/components/EventTimeline.tsx` | Add new NCS event type mappings and render logic. | Keep Python and TypeScript mappings in sync; add tests in `test_webhooks.py`. |
| `web.conversation-ui` | `web/src/components/*`, `web/src/lib/conversation.ts` | Customize pre-call, transcript, metrics, `EventTimeline`, or controls. | Preserve SSE subscription lifecycle and `sessionId` correlation. |
| `verification.contracts` | `web/scripts/*.ts`, root `package.json` | Add checks for new browser/backend boundaries. | Keep checks runnable without live Agora credentials. |

## Invariants

- Browser code calls only `/api/get_config`, `/api/startAgent`, `/api/stopAgent`, `/api/ncsNotify`, `/api/webhooks/stream`, and `/api/webhooks/reset` for the default flow.
- Next.js owns `/api/*` through rewrites only; no `web/app/api/**/route.ts` for agent/token logic.
- FastAPI owns token generation, `AGORA_APP_CERTIFICATE`, `AGORA_NOTIFICATION_SECRET`, and agent + receiver lifecycle.
- A cascading managed-OpenAI pipeline handles voice; `.with_labels` attaches the correlation label every session.
- The NCS receiver uses verify-if-secret-set: no `AGORA_NOTIFICATION_SECRET` → dev mode (no signature enforcement); with it → HMAC-SHA256 required.
- The backend issues one RTC+RTM-capable token for a concrete non-zero UID.

## Stable Contracts

| Contract | Stable shape |
| -------- | ------------ |
| Required backend env | `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE` |
| Optional backend env | `AGORA_NOTIFICATION_SECRET`, `WEBHOOKS_DB_PATH`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `AGENT_GREETING`, `PORT` (env only) |
| Required web deploy env | `AGENT_BACKEND_URL` |
| `GET /api/get_config` | Query `channel?`, `uid?`; returns `data.app_id`, `data.token`, `data.uid`, `data.channel_name`, `data.agent_uid`. |
| `POST /api/startAgent` | Body `{ channelName, rtcUid, userUid, sessionId?, parameters? }`; returns `data.agent_id`, `data.channel_name`, `data.status`. |
| `POST /api/stopAgent` | Body `{ agentId }`; returns `{ code: 0, msg: "success" }`. |
| `POST /api/ncsNotify` | Raw body + `Agora-Signature-V2` header; returns `{ code: 0, msg: "success" }` (200) or `{ code: 1, msg: "invalid signature" }` (401). |
| `GET /api/webhooks/stream` | SSE; `data:<json>\n\n` frames; keepalives `: keepalive\n\n`; replays `recent_events()` on connect. |
| `POST /api/webhooks/reset` | Returns `{ code: 0, msg: "cleared" }`. |
| Success envelope | `{ "code": 0, "msg": "success", "data": ... }` where the route has data. |
| Verification entry points | `bun run verify:web`, `bun run verify:backend`, `bun run verify:web:proxy`, `bun run verify:local:fastapi`, `bun run verify:local`. |

## Internal / Subject to Change

- Visual layout, component composition, Tailwind classes, and assets under `web/src/components/`.
- Exact model name, VAD timing, voice, and greeting text, as long as they stay documented extension points.
- In-memory `Agent._sessions` details; the stable behavior is start by channel/user and stop by returned `agent_id`.
- SQLite schema details beyond the stable `WebhookEvent` record shape (`id`, `eventType`, `notifyMs`, `sid`, `payload`, `receivedMs`).
- `SseHub` internals; the stable behavior is fan-out of stored events to SSE subscribers with keepalives.
- Verification internals under `web/scripts/`; the stable surface is the root script names and what they assert.
- `agora-agents` SDK minor-version behavior; this recipe lower-bounds `>=2.3.0` but does not freeze every field.

## Related Progressive Disclosure Docs

- `L1/01_setup.md` — setup, env, and commands.
- `L1/02_architecture.md` — request/callback flow and topology.
- `L1/05_workflows.md` — common modification workflows.
- `L1/06_interfaces.md` — route, rewrite, env, SSE, and `WebhookEvent` contracts.
- `L1/L2/webhook_receiver.md` — full NCS receiver detail.
- `L1/L2/session_lifecycle.md` — browser sessionId, SSE subscription, RTC/RTM orchestration.
