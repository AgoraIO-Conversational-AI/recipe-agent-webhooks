**When to Read This:** Load this document when touching client-side join/teardown, the per-tab `sessionId` correlation, token renewal, the SSE subscription lifecycle, or anything in `LandingPage.tsx` that coordinates multiple async steps.

# Session Lifecycle — Deep Dive

The browser orchestrates several concurrent setup steps before the conversation starts, and also maintains a persistent SSE connection to the webhook timeline independently of the conversation state.

## Per-tab Session ID

`LandingPage.tsx` generates one `sessionId` per mount:

```typescript
const sessionId = useMemo(() => crypto.randomUUID(), [])
```

This UUID is:
1. Passed to `startAgent(..., sessionId)` → forwarded to the backend as `StartAgentRequest.sessionId`.
2. Used by the backend to set the agent label: `{"recipe": "webhooks", "session": sessionId}`.
3. Agora's cloud carries this label in NCS payloads back to `/ncsNotify`.
4. `EventTimeline` receives `ownSession={sessionId}` and highlights rows where `payload.labels.session === ownSession`.

If `sessionId` is not provided (or the request omits it), the backend synthesizes one:
```python
label_session = session_id or f"agent_{channel_name}_{agent_uid}_{int(time.time())}"
```

## SSE Subscription

The SSE subscription starts immediately on component mount — independent of whether a conversation is active:

```typescript
useEffect(() => {
    const unsubscribe = subscribeWebhooks((event) =>
        setWebhookEvents((prev) => [...prev, event].slice(-200)),
    )
    return unsubscribe
}, [])
```

- `subscribeWebhooks` opens an `EventSource('/api/webhooks/stream')`.
- On connect, the server replays `recent_events()` (up to 100, oldest-first), then streams new events live.
- The client caps the in-memory list at 200 events (`.slice(-200)`).
- The cleanup function (`return unsubscribe`) closes the `EventSource` on unmount.
- The SSE connection is completely separate from the RTC/RTM connection — it remains open even when no agent is running.

## Conversation Start Flow

`handleStartConversation()` runs two async operations in parallel then joins:

```typescript
const [agentIdResult, rtm] = await Promise.all([
    startAgent(config.channel_name, Number(config.agent_uid), Number(config.uid), sessionId)
        .catch((err) => { setAgentJoinError(true); return undefined }),
    (async () => {
        const rtm = new AgoraRTM.RTM(appId, config.uid)
        await rtm.login({ token: config.token })
        await waitForRtmConnected(rtm, 600)  // 600 ms timeout, then proceed anyway
        await rtm.subscribe(config.channel_name)
        return rtm
    })(),
])
```

Before the parallel step, `getConfig()` is called to obtain `app_id`, `token`, `uid`, `channel_name`, and `agent_uid`.

Key design decisions:
- Agent start failure is non-fatal — `agentJoinError` is set and the conversation continues (the user can still join audio, just without a working agent).
- RTM login has a 600 ms timeout (`waitForRtmConnected`); if the RTM client doesn't reach `CONNECTED` in time, the flow proceeds anyway to avoid blocking.
- Token from `getConfig` is used for both RTC join (passed to `useJoin`) and RTM login.

## RTC Join (ConversationComponent)

`ConversationComponent` uses `agora-rtc-react`'s `useJoin` hook:

```typescript
const { isConnected: joinSuccess } = useJoin(
    { appid, channel, token, uid: parseInt(agoraData.uid, 10) },
    isReady,
)
```

`isReady` is set via a `setTimeout(..., 0)` in a `useEffect` to avoid StrictMode double-invocation. Once `joinSuccess` is true, `AgoraVoiceAI.init()` subscribes to transcript, agent state, metrics, and error events.

## Token Renewal

`handleTokenWillExpire` renews both the RTC and RTM tokens:

```typescript
const [rtcConfig, rtmConfig] = await Promise.all([
    getConfig({ channel, uid }),              // renew RTC token for this uid
    getConfig({ channel, uid: agoraData.uid }),// renew RTM token for the RTM login uid
])
return { rtcToken: rtcConfig.token, rtmToken: rtmConfig.token }
```

Both are minted via `generate_convo_ai_token` (Token007, 3600 s expiry).

## Conversation End Flow

`handleEndConversation()` in `LandingPage.tsx`:
1. Calls `stopAgent(agoraData.agentId)` (if `agentId` exists) → backend sends the stop request to Agora ConvoAI, which produces a `102` NCS callback.
2. Calls `rtmClient.logout()`.
3. Clears `agoraData`, `rtmClient`, and `showConversation`.

`ConversationComponent.handleEndConversation`:
1. Unpublishes the microphone track.
2. Stops and closes the track.
3. Calls the parent `onEndConversation()`.

The SSE subscription is **not** closed on conversation end — the timeline remains live and continues to show any subsequent events.

## EventTimeline State

`webhookEvents` is managed in `LandingPage.tsx` and passed down to `EventTimeline`. The **Clear** button in `EventTimeline` calls `resetWebhooks()` (which POSTs to `/api/webhooks/reset`) and then `onClear()` (which clears the local `webhookEvents` state). These are independent — clearing the server store does not automatically clear the local array, and vice versa.
