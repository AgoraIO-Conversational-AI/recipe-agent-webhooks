'use client'
import { type WebhookEvent, webhookEventName, resetWebhooks } from '@/services/api'

function sessionOf(e: WebhookEvent): string | undefined {
  const labels = (e.payload?.labels ?? {}) as Record<string, string>
  return labels.session
}

export function EventTimeline({ events, ownSession, onClear }: {
  events: WebhookEvent[]; ownSession?: string; onClear: () => void
}) {
  return (
    <div className="event-timeline">
      <div className="event-timeline__header">
        <h2>Server-side webhook events</h2>
        <button type="button" onClick={async () => { await resetWebhooks(); onClear() }}>Clear</button>
      </div>
      {events.length === 0 ? (
        <p className="event-timeline__empty">
          No events yet. Configure Agora Console → Notifications to POST to <code>/ncsNotify</code>
          (see README), then start an agent.
        </p>
      ) : (
        <ul>
          {events.map((e) => {
            const mine = ownSession && sessionOf(e) === ownSession
            const channel = (e.payload?.channelName as string) ?? ''
            const reason = (e.payload?.leaveReason ?? e.payload?.reason) as string | undefined
            return (
              <li key={e.id} className={mine ? 'event-row event-row--mine' : 'event-row'}>
                <span className="event-row__name">{webhookEventName(e.eventType)}</span>
                {channel && <span className="event-row__channel">{channel}</span>}
                {reason && <span className="event-row__reason">reason: {reason}</span>}
                <time>{new Date(e.receivedMs).toLocaleTimeString()}</time>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export default EventTimeline
