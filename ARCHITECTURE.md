# Architecture — Events Recipe

Two processes. The browser talks only to Next.js `/api/*`, which rewrites to the
agent backend. The agent backend owns Agora tokens and agent lifecycle. OpenAI is
Agora-managed (keyless) — no separate LLM service is needed.

The net-new work in this recipe is entirely in the web layer: a unified
`EventTimeline` component and an annotated transcript. The backend has no special
logic — it only enables the three built-in event flags.

## Request flow

```
Browser
  │  GET /api/get_config            → token + channel/UIDs
  │  POST /api/startAgent           → start agent session
  ▼
Next.js  (rewrites /api/* → AGENT_BACKEND_URL)
  ▼
Agent backend (server/, :8000)
  │  builds session with:
  │    OpenAI(model=OPENAI_MODEL, system_messages=[friendly assistant])
  │    parameters: data_channel=rtm, enable_metrics=true,
  │                enable_error_message=true
  │    advanced_features: enable_rtm=true
  ▼
Agora ConvoAI Cloud
  │  user speech → Deepgram STT (managed, nova-3, en)
  │  text → OpenAI (Agora-managed, keyless)
  │  reply → MiniMax TTS (managed)
  │  RTM events → browser:
  │    AGENT_STATE_CHANGED, AGENT_METRICS, AGENT_ERROR,
  │    MESSAGE_ERROR, TRANSCRIPT_UPDATED
  ▼
EventTimeline + annotated transcript in the web UI
```

`POST /api/stopAgent { agentId }` ends the session.

## Why no llm/ service

This recipe uses the **managed OpenAI vendor**
(`agora_agent.agentkit.vendors.OpenAI`). Agora holds the OpenAI API key on its
cloud; the recipe is zero-key by default. An optional `OPENAI_API_KEY` env var
lets you bring your own account if needed.

This means:
- No `llm/` service to expose publicly.
- No tunnel required.
- The only required credentials are `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`.

## Event surface

All events arrive over RTM. The web client uses `AgoraVoiceAI` from
`agora-agent-client-toolkit` to subscribe. Each event is appended to a
`TimelineEvent[]` buffer (capped at 50) and rendered by `EventTimeline`.

| SDK event | Kind | What it carries |
| --- | --- | --- |
| `AGENT_STATE_CHANGED` | `state` | `listening`, `thinking`, `speaking`, `idle` |
| `AGENT_METRICS` | `metric` | Stage type, metric name, value (ms) |
| `AGENT_ERROR` | `error` | Error type + message |
| `MESSAGE_ERROR` | `error` | RTM message error code + message |
| `TRANSCRIPT_UPDATED` | `turn` | Role (agent/user) + text snippet |

> **Limitation:** only the built-in events listed above are available. There
> is no server-side custom-event API in this recipe.

## API (agent backend, port 8000)

| Endpoint | Method | Description |
| --- | --- | --- |
| `/get_config` | GET | Token + channel/UID config |
| `/startAgent` | POST | Start the events agent session |
| `/stopAgent` | POST | Stop the agent by `agent_id` |

The browser calls these as `/api/*`; Next rewrites them to `AGENT_BACKEND_URL`.

## Auth

- Browser → agent backend: none (local dev).
- Agent backend → Agora cloud: Token007, generated from `AGORA_APP_ID` +
  `AGORA_APP_CERTIFICATE`.
- Agora cloud → OpenAI: Agora-managed key (transparent to this recipe).
  Optionally overridden by `OPENAI_API_KEY` if provided.
