# 06 · Interfaces

> Boundary contracts: backend routes, the `/api/*` rewrite map, env vars, the response envelope, SSE wire format, and the `WebhookEvent` type.

## Backend routes (port 8000)

The browser calls these as `/api/<name>`; Next rewrites to the backend `/<name>`.

### `GET /get_config`

- Query (optional): `channel?: string`, `uid?: int` (≤ 0 or missing → backend generates one).
- Returns `data`: `{ app_id, token, uid (string), channel_name, agent_uid (string) }`.
- Token is a Token007 RTC+RTM token, expiry 3600 s, for a concrete non-zero UID.

### `POST /startAgent`

- Body: `{ channelName: string, rtcUid: int, userUid: int, sessionId?: string, parameters?: object }`.
  - `sessionId` is attached as a correlation label on the agent (`{"recipe": "webhooks", "session": sessionId}`).
  - `parameters.output_audio_codec?: string` is the only honored parameter field.
- Returns `data`: `{ agent_id, channel_name, status: "started" }`.
- 400 if `channelName`/`rtcUid`/`userUid` invalid.

### `POST /stopAgent`

- Body: `{ agentId: string }`.
- Returns `{ code: 0, msg: "success" }` (no `data`).

### `POST /ncsNotify`

- Receives Agora NCS callback payloads. Reads the raw body + `Agora-Signature-V2` header.
- Returns `{ code: 0, msg: "success" }` (200) when accepted.
- Returns `{ code: 1, msg: "invalid signature" }` (401) when signature verification fails.
- Stores accepted events append-only; publishes to `SseHub`.

### `GET /webhooks/stream`

- Content-Type: `text/event-stream` (SSE).
- On connect: replays `recent_events()` (up to 100, oldest-first, newest last) as `data: <json>\n\n` frames.
- After replay: streams new events live as they arrive from `SseHub`.
- Keepalive: sends `: keepalive\n\n` every 15 s of inactivity.
- Disconnects cleanly when the client closes.

### `POST /webhooks/reset`

- No body required.
- Returns `{ code: 0, msg: "cleared" }` (no `data`).

## Response envelope

```json
{ "code": 0, "msg": "success", "data": { } }
```

`data` omitted when the route has no payload. Non-zero `code` or missing `data` = error on the client side. Exception: `/webhooks/reset` uses `msg: "cleared"`.

## Rewrite map (`web/next.config.ts`)

| Browser path               | Backend destination        |
| -------------------------- | -------------------------- |
| `/api/get_config`          | `/get_config`              |
| `/api/startAgent`          | `/startAgent`              |
| `/api/stopAgent`           | `/stopAgent`               |
| `/api/ncsNotify`           | `/ncsNotify`               |
| `/api/webhooks/stream`     | `/webhooks/stream`         |
| `/api/webhooks/reset`      | `/webhooks/reset`          |

`rewrites()` returns `[]` when `AGENT_BACKEND_URL` is unset. The contract is asserted by `verify-api-contracts.ts` and exercised by `verify-local-proxy.ts`.

## Browser API client (`web/src/services/api.ts`)

- `getConfig({ channel?, uid? }) → GetConfigResponse`
- `startAgent(channelName, rtcUid, userUid, sessionId?) → agent_id`
- `stopAgent(agentId) → void`
- `subscribeWebhooks(onEvent) → () => void` — opens an `EventSource` to `/api/webhooks/stream`; returns a cleanup function.
- `resetWebhooks() → void` — `POST /api/webhooks/reset`.
- `webhookEventName(eventType) → string` — maps `101` → "Agent started", `102` → "Agent stopped", null → "Event", other → `"Event <n>"`.

## `WebhookEvent` type (`web/src/services/api.ts`)

```typescript
interface WebhookEvent {
  id: number
  eventType: number | null
  notifyMs: number | null
  sid: string | null
  payload: Record<string, unknown>
  receivedMs: number
}
```

`payload.labels.session` carries the correlation label. `payload.channelName` and `payload.leaveReason` are present on `101`/`102` events where Agora provides them.

## Environment variables

| Variable                    | Scope        | Required | Default              |
| --------------------------- | ------------ | :------: | -------------------- |
| `AGORA_APP_ID`              | backend      |    ✅    | —                    |
| `AGORA_APP_CERTIFICATE`     | backend      |    ✅    | —                    |
| `AGORA_NOTIFICATION_SECRET` | backend      |          | — (dev mode if unset) |
| `WEBHOOKS_DB_PATH`          | backend      |          | `/tmp/webhooks.db`   |
| `OPENAI_API_KEY`            | backend      |          | — (Agora-managed by default) |
| `OPENAI_MODEL`              | backend      |          | `gpt-4o-mini`        |
| `AGENT_GREETING`            | backend      |          | built-in line        |
| `AGENT_BACKEND_URL`         | web (deploy) |  ✅\*    | `http://localhost:8000` (dev) |
| `PORT`                      | backend (env only) |    | `8000` — do **not** put in `.env.example` |

\* Required wherever the web app is deployed; rewrites are empty without it.

## Related Deep Dives

- [webhook_receiver](L2/webhook_receiver.md) — full SQLite schema, HMAC-SHA256 details, SSE keepalive behavior.
