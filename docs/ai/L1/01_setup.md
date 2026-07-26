# 01 · Setup

> Install dependencies, configure env, and run the webhooks recipe locally. This recipe is **zero provider-key** by default: `OPENAI_API_KEY` is optional (Agora manages the OpenAI key). To receive real NCS callbacks, a public tunnel and Agora Console registration are required.

## Prerequisites

- Python 3.10+ (backend runs on 3.10 and 3.13 in CI)
- [Bun](https://bun.sh/) (runs the web app and orchestration scripts)
- [Agora CLI](https://github.com/AgoraIO/cli) (optional; easiest way to mint App ID + Certificate)
- [ngrok](https://ngrok.com/) or any public tunnel — required to receive live NCS callbacks

## Install

```bash
bun run setup            # installs web deps + creates server/ venv from requirements.txt
```

`setup` runs `setup:env` (copies `server/.env.example` → `server/.env.local` if missing), `setup:server` (recreates `server/venv`, installs `requirements.txt`), and `setup:web` (`bun install`).

## Configure env

Backend env file is `server/.env.local` (template: `server/.env.example`).

| Variable                      | Required | Default              | Notes                                                                              |
| ----------------------------- | :------: | -------------------- | ---------------------------------------------------------------------------------- |
| `AGORA_APP_ID`                |    ✅    | —                    | Agora Console → Project → App ID                                                   |
| `AGORA_APP_CERTIFICATE`       |    ✅    | —                    | Agora Console → Project → App Certificate                                          |
| `AGORA_NOTIFICATION_SECRET`   |          | —                    | Optional. Agora Console → Notifications secret. Enables HMAC-SHA256 verification. **Not** an LLM key. |
| `WEBHOOKS_DB_PATH`            |          | `/tmp/webhooks.db`   | Where received events are stored. Ephemeral by default; gitignored.                |
| `OPENAI_API_KEY`              |          | —                    | Optional BYO key. Agora manages OpenAI by default (keyless).                       |
| `OPENAI_MODEL`                |          | `gpt-4o-mini`        | OpenAI model name                                                                  |
| `AGENT_GREETING`              |          | built-in line        | Optional opening utterance override                                                |

Fill credentials via the Agora CLI or by hand:

```bash
agora login
agora project use <your-project>
agora project env write server/.env.local   # writes App ID + Certificate
# AGORA_NOTIFICATION_SECRET, OPENAI_API_KEY, etc. added by hand if needed
```

> Do **not** add `PORT` to `server/.env.example` — see [07_gotchas](07_gotchas.md).

## Run

```bash
bun run dev              # backend (:8000) + web (:3000) via concurrently
```

Open <http://localhost:3000>. The **Server-side webhook events** timeline is visible immediately. Backend API docs at <http://localhost:8000/docs>.

To receive real NCS callbacks:

1. Tunnel the backend: `ngrok http 8000`
2. Register `https://<ngrok>/ncsNotify` in Agora Console → Notifications → Conversational AI events (Business ID 17), events `101` and `102`.
3. Optionally copy the Console secret into `AGORA_NOTIFICATION_SECRET`.

## Quick commands

```bash
bun run doctor           # shared prereqs (bun + node_modules); no creds needed
bun run doctor:local     # + .env.local + AGORA_APP_ID/CERTIFICATE present
bun run verify           # web-only gate (doctor + api contracts + web build)
bun run verify:local     # full local gate: backend compile + fastapi smoke + proxy + web build
bun run clean            # remove venvs and build artifacts
```

Backend unit tests run standalone (no cloud, no creds):

```bash
cd server && pytest tests -v
```

## Related Deep Dives

- None. For what each verify command asserts, see [05_workflows](05_workflows.md) and [06_interfaces](06_interfaces.md).
