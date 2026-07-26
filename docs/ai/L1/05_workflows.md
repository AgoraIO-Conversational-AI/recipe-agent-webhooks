# 05 · Workflows

> Step-by-step guides for the common changes in this recipe. Each ends with the narrowest verify command to run.

## Add or change a browser-facing route

1. Add the FastAPI handler in `server/src/server.py` (or in `webhooks.py` for receiver-related routes). Return the `{ code, msg, data }` envelope.
2. Add the `/api/<name>` → `/<name>` mapping in `web/next.config.ts` `rewrites()`.
3. Add a client helper in `web/src/services/api.ts`.
4. Extend `web/scripts/verify-api-contracts.ts` with the new path + envelope assertions.
5. Verify: `bun run verify:web` (and `bun run verify:local:fastapi` if it should go through the real backend).

## Change the agent prompt / greeting / model

1. Greeting: set `AGENT_GREETING` (env) or edit the default in `server/src/agent.py`.
2. Model: set `OPENAI_MODEL` (default `gpt-4o-mini`).
3. Other pipeline options (VAD, codec, audio scenario): edit `Agent.start()` in `server/src/agent.py`.
4. Verify: `bun run verify:backend` (compile) + `cd server && pytest tests -v`.

## Add a new NCS event type

1. Add the mapping to `_EVENT_NAMES` in `server/src/webhooks.py` (e.g. `{201: "Some event"}`).
2. Update `event_display_name` if fallback formatting needs to change.
3. Update `webhookEventName` in `web/src/services/api.ts` to match.
4. Update the `EventTimeline` if the new event type needs different rendering.
5. Verify: `cd server && pytest tests/test_webhooks.py -v`.

## Enable / change signature verification

1. Set `AGORA_NOTIFICATION_SECRET` in `server/.env.local` to match the Agora Console NCS secret.
2. The receiver immediately enforces verification — no code change needed.
3. Verify by sending a test notification from the Console (or by using `pytest tests/test_webhooks.py -k verify`).

## Receive real NCS callbacks locally

1. Start the stack: `bun run dev`.
2. Tunnel the backend: `ngrok http 8000`.
3. Register the public URL in Agora Console → Notifications → Conversational AI (Business ID 17), events `101` and `102`.
4. Optionally copy the Console secret into `AGORA_NOTIFICATION_SECRET`.
5. Start and stop an agent in the web UI. Events `101` and `102` should appear in the timeline within a few seconds.

## Run / debug locally

```bash
bun run dev              # both processes
bun run doctor:local     # check creds + .env.local before a live call
```

## Verify before finishing

| Change touches…                    | Run                                                                   |
| ---------------------------------- | --------------------------------------------------------------------- |
| Web only                           | `bun run verify:web`                                                  |
| Backend logic / agent config       | `bun run verify:backend` + `cd server && pytest tests -v`             |
| Route/proxy boundary               | `bun run verify:web:proxy` and/or `bun run verify:local:fastapi`      |
| `webhooks.py` (receiver / SSE)     | `cd server && pytest tests/test_webhooks.py -v`                       |
| Anything end-to-end (local)        | `bun run verify:local`                                                |

## Deploy

1. Deploy `web/` as a Next.js app.
2. Deploy `server/` (or any reachable FastAPI host). The published backend-only image is `ghcr.io/AgoraIO-Conversational-AI/recipe-agent-webhooks` on `v*` tags.
3. Set `AGENT_BACKEND_URL` in the web deployment so rewrites reach the backend.
4. Register the deployed `https://<your-backend>/ncsNotify` in Agora Console → Notifications.
5. Optionally set `AGORA_NOTIFICATION_SECRET` in the backend's production env.

## Related Deep Dives

- [webhook_receiver](L2/webhook_receiver.md) — NCS receiver internals, signature algorithm, SSE wire format.
- [session_lifecycle](L2/session_lifecycle.md) — client-side join/SSE-subscription/teardown flow.
