# 08 · Security

> Trust boundaries, secret handling, and auth for the webhooks recipe.

## Trust boundaries

| Hop                              | Auth                                                                              |
| -------------------------------- | --------------------------------------------------------------------------------- |
| Browser → agent backend          | None in local dev (the `/api/*` rewrite is same-origin).                          |
| Agent backend → Agora cloud      | Token007, generated from `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`.                |
| Agora cloud → agent backend (NCS)| `Agora-Signature-V2` HMAC-SHA256 header, verified against `AGORA_NOTIFICATION_SECRET` when set (dev mode otherwise). |
| Agora cloud → OpenAI             | Agora-managed key (transparent to this recipe). Optionally overridden by `OPENAI_API_KEY`. |

## Secret handling

- **Server-only secrets:** `AGORA_APP_CERTIFICATE` and `AGORA_NOTIFICATION_SECRET` live only in `server/.env.local` and never reach the browser.
- The browser receives a short-lived RTC+RTM token, never the certificate or the NCS secret.
- `OPENAI_API_KEY`, when set, is also server-only — passed to the `OpenAI` vendor, never returned to clients.
- `server/.env.local` is gitignored; `server/.env.example` ships placeholder keys only.
- Tokens (`generate_convo_ai_token`) expire after 3600 s and are minted per `get_config` call for a concrete non-zero UID.

## NCS signature verification

When `AGORA_NOTIFICATION_SECRET` is set:
- The receiver reads the raw request body (bytes) and the `Agora-Signature-V2` header.
- Expected signature: `hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()`.
- Comparison uses `hmac.compare_digest` (constant-time).
- Mismatches return 401 `{ "code": 1, "msg": "invalid signature" }` without storing the event.

When `AGORA_NOTIFICATION_SECRET` is **not** set, all callbacks are accepted (dev mode). Do not enable this in production without setting the secret.

## CORS

The backend sets `CORSMiddleware` with `allow_origins=["*"]` — open by design for a local/dev recipe. **Lock this down to known origins before any production deployment.**

## Validation

- `Agent.start()` rejects empty `channel_name` and non-positive `agent_uid`/`user_uid` before issuing tokens or starting a session.
- Route errors are sanitized: `_log_route_error` logs only non-`None` context; exceptions map to 400/500 without leaking internals to the client beyond the message string.
- The NCS receiver does not validate the `payload` contents beyond JSON parsing — it stores the raw payload verbatim.

## Deployment notes

- Set `AGENT_BACKEND_URL` only to a backend you control; the rewrite forwards browser requests there verbatim.
- Register `https://<your-backend>/ncsNotify` in the Agora Console and set `AGORA_NOTIFICATION_SECRET` in the backend's production env.
- The published Docker image is **backend-only** (`:8000`); it does not bundle secrets. Set env vars at runtime.
- `WEBHOOKS_DB_PATH` defaults to `/tmp/webhooks.db` (ephemeral). Set a persistent path for production.

## Related Deep Dives

- [webhook_receiver](L2/webhook_receiver.md) — full HMAC-SHA256 signature flow and dev-mode bypass detail.
