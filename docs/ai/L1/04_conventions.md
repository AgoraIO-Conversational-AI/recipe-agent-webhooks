# 04 · Conventions

> Coding patterns shared across `server/` and `web/`. Follow these to keep local and deployed modes aligned, and to keep the NCS receiver correct.

## Boundary ownership

- Browser code calls only `/api/*`. Backend placement is hidden behind Next rewrites (`web/next.config.ts`).
- **Never** add `web/app/api/**/route.ts` for agent/token logic — `verify-api-contracts.ts` fails the build if a `route.ts` appears under `app/api`.
- Token generation, the App Certificate, and the NCS secret (`AGORA_NOTIFICATION_SECRET`) stay in `server/`.

## Backend (Python / FastAPI)

- Async throughout: route handlers are `async def`; the agent uses `AsyncAgora` and `create_async_session`.
- Request bodies are Pydantic models (`StartAgentRequest`, `StopAgentRequest`). Field names are **camelCase** (`channelName`, `rtcUid`, `userUid`) to match the browser client. `StartAgentRequest` also accepts optional `sessionId` for the webhook correlation label.
- Error mapping is centralized: `_to_http_error()` maps `ValueError → 400`, `RuntimeError → 500`, else 500. Raise plain `ValueError`/`RuntimeError`; let the route convert.
- Logging via `logging.getLogger("uvicorn.error")`.
- Env read with `os.getenv`; `.env.local` then `.env` loaded with `override=True`.

## Response envelope

All backend JSON responses use:

```json
{ "code": 0, "msg": "success", "data": { } }
```

`data` is present only when the route returns a payload. The browser client treats `code !== 0` (or missing `data`) as an error. Exception: `/webhooks/reset` returns `{ "code": 0, "msg": "cleared" }` (no `data`).

## Webhook receiver (`webhooks.py`)

- The receiver is a self-contained module — store, signature, hub, and router all live in `webhooks.py`. Mount with `app.include_router(webhooks.router)`.
- **Verify-if-secret-set:** `verify_signature` returns `True` when no secret is configured; requires a matching `Agora-Signature-V2` HMAC-SHA256 when one is set. Dev mode logs `"dev mode: webhook signature unverified"`.
- `recent_events()` returns oldest-first (newest last) for the timeline. The limit is 100 by default.
- The `SseHub` is module-level; it is shared across requests. `subscribe` returns an `asyncio.Queue`; `unsubscribe` removes it. Keepalives (`: keepalive\n\n`) are sent every 15 s of inactivity.
- `parse_event` retains the raw NCS `payload` verbatim. Do not discard unknown fields.

## Agent pipeline + labels

- This is a cascading pipeline: `DeepgramSTT(nova-3, en)` → `OpenAI` (managed, keyless) → `MiniMaxTTS`. Do not introduce `with_mllm` or realtime patterns.
- Attach `.with_labels({"recipe": "webhooks", "session": label_session})` every time. `label_session` defaults to a synthetic name if `session_id` is not provided.
- Do not introduce `llm/` or a `CustomLLM` vendor.

## Web (TypeScript / Next.js)

- Lint/format with Biome (`bun run lint`, `bun run lint:fix` in `web/`).
- RTC client creation must be StrictMode-safe (strict mode is on).
- `subscribeWebhooks` / `resetWebhooks` / `WebhookEvent` are exported from `src/services/api.ts`. The UI never calls SSE or backend directly.
- The `EventTimeline` receives `events: WebhookEvent[]` and `ownSession?: string` as props; session correlation is done in the component by reading `payload.labels.session`.

## Testing approach

- Backend: `pytest` in `server/`, standalone — `conftest.py` fakes env and SDK session, no cloud or real creds needed.
- Web: contract/proxy/fastapi smoke scripts under `web/scripts/` run without live Agora calls.
- Run the **narrowest** relevant verify command before finishing (see [05_workflows](05_workflows.md)).

## Doc upkeep

When you change request/response contracts, env vars, or workflow, update the web client, backend, contract checks, README, **and** the matching `docs/ai/L1/` file together, then bump `Last Reviewed` in [L0](../L0_repo_card.md).

## Related Deep Dives

- [webhook_receiver](L2/webhook_receiver.md) — signature algorithm, SQLite schema, SSE wire format details.
