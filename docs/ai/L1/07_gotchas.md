# 07 · Gotchas

> Non-obvious pitfalls specific to the webhooks recipe. Read before changing the receiver, agent, env, or verify scripts.

## No NCS events without a public tunnel

NCS callbacks come from Agora's cloud — the backend must be reachable from the internet. A local `bun run dev` alone will not receive callbacks. Tunnel the backend (`ngrok http 8000`) and register the public URL in Agora Console → Notifications before testing the live flow.

## Dev mode: signature unverified

When `AGORA_NOTIFICATION_SECRET` is not set, `verify_signature` returns `True` for all callbacks and the receiver logs `"dev mode: webhook signature unverified"`. This is intentional — don't move the secret check into `__init__` or make it required to boot.

## Receiver returns 401 — secret mismatch

If `AGORA_NOTIFICATION_SECRET` is set and the `Agora-Signature-V2` header is missing or wrong, the receiver returns 401 and stores nothing. Re-copy the Console secret, or unset the env var to run in dev mode. The signature is computed over the **raw request body** (bytes), not the decoded JSON.

## SQLite DB is ephemeral by default

`WEBHOOKS_DB_PATH` defaults to `/tmp/webhooks.db`. The file is gitignored. On Docker restart or ephemeral filesystem, history is lost. Set `WEBHOOKS_DB_PATH` to a persistent path for production. The **Clear** button (`POST /webhooks/reset`) deletes all rows.

## `recent_events()` returns oldest-first

Despite the SQL `ORDER BY id DESC LIMIT ?`, `_row_to_record` reverses the list before returning. The timeline always shows oldest at top, newest at bottom. Do not change this ordering.

## SSE fan-out is in-process only

`SseHub` is a module-level object using in-memory `asyncio.Queue`. It does not span multiple FastAPI workers or processes. Running with multiple Gunicorn workers will lose events for clients connected to different workers. For production multi-worker deployments, replace with a Redis pub/sub or similar.

## `sessionId` is browser-generated

The browser generates a `crypto.randomUUID()` per tab mount (in `LandingPage.tsx`). If `sessionId` is not provided to `/startAgent`, the backend synthesizes one (`agent_{channel}_{uid}_{timestamp}`). Timeline rows are highlighted only when `payload.labels.session` matches the current tab's `sessionId` exactly.

## Do not put `PORT` in `server/.env.example`

`verify:local:fastapi` injects a random `PORT` and loads env with `load_dotenv(override=True)`. A `PORT` line in `.env.example` (copied to `.env.local`) would clobber the injected port and break the smoke test.

## Keep `/api/*` ownership in rewrites

Adding `web/app/api/**/route.ts` for agent/token logic breaks the boundary — `verify-api-contracts.ts` explicitly fails if a `route.ts` exists under `app/api`. Token and receiver logic belong in `server/`.

## camelCase request fields

`StartAgentRequest` uses `channelName`, `rtcUid`, `userUid` (camelCase) to match the browser client. Renaming one side without the other breaks contract tests.

## OpenAI is Agora-managed (keyless)

`OPENAI_API_KEY` is optional. The `OpenAI` vendor passes `api_key=None` to the SDK when the env var is not set — Agora's cloud holds the key. Set it only if your account specifically requires BYO key access.

## Local calls under a global proxy

Global proxies (Clash, etc.) can break `localhost`/RFC-1918 traffic. Configure the proxy to send `127.0.0.1`, `localhost`, and private ranges DIRECT, or use `socksio` (in `requirements.txt`) plus `all_proxy` to route through SOCKS.

## Related Deep Dives

- [webhook_receiver](L2/webhook_receiver.md) — signature algorithm detail, SQLite behavior, SSE hub internals.
