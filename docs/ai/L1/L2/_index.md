# Deep Dives Index

| Document                                              | Summary                                                                          | Load When                                                                    |
| ----------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [webhook_receiver.md](webhook_receiver.md)            | Full NCS receiver internals: HMAC-SHA256 signature flow, SQLite schema, SSE wire format, `SseHub` lifecycle | Changing signature verification, the SQLite store, SSE behavior, or adding NCS event types |
| [session_lifecycle.md](session_lifecycle.md)          | Browser orchestration: per-tab sessionId, get_config + start/stop, SSE subscription, RTC/RTM join, EventTimeline | Touching client-side join, SSE subscription, token renewal, or webhook correlation |
