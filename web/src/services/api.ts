const API_BASE_URL = '/api'

export interface GetConfigResponse {
  app_id: string
  token: string
  uid: string
  channel_name: string
  agent_uid: string
}

export async function getConfig(options?: { channel?: string; uid?: string | number }): Promise<GetConfigResponse> {
  const params = new URLSearchParams()
  if (options?.channel !== undefined && options.channel !== '') {
    params.set('channel', options.channel)
  }
  if (options?.uid !== undefined && options.uid !== '') {
    params.set('uid', String(options.uid))
  }

  const query = params.toString()
  const response = await fetch(`${API_BASE_URL}/get_config${query ? `?${query}` : ''}`, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  const result = await response.json()
  if (result.code !== 0 || !result.data) {
    throw new Error(result.msg || 'Failed to get configuration')
  }
  return result.data
}

export async function startAgent(channelName: string, rtcUid: number, userUid: number, sessionId?: string): Promise<string> {
  const payload = { channelName, rtcUid, userUid, sessionId }
  const response = await fetch(`${API_BASE_URL}/startAgent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
  const result = await response.json()
  if (result.code !== 0 || !result.data?.agent_id) {
    throw new Error(result.msg || 'Failed to start agent')
  }
  return result.data.agent_id
}

export interface WebhookEvent {
  id: number
  eventType: number | null
  notifyMs: number | null
  sid: string | null
  payload: Record<string, unknown>
  receivedMs: number
}

export function subscribeWebhooks(onEvent: (e: WebhookEvent) => void): () => void {
  const source = new EventSource('/api/webhooks/stream')
  source.onmessage = (msg) => {
    try { onEvent(JSON.parse(msg.data) as WebhookEvent) } catch { /* ignore keepalives */ }
  }
  return () => source.close()
}

export async function resetWebhooks(): Promise<void> {
  await fetch('/api/webhooks/reset', { method: 'POST' })
}

export function webhookEventName(eventType: number | null): string {
  if (eventType === 101) return 'Agent started'
  if (eventType === 102) return 'Agent stopped'
  return eventType == null ? 'Event' : `Event ${eventType}`
}

export async function stopAgent(agentId: string): Promise<void> {
  if (!agentId) return

  const response = await fetch(`${API_BASE_URL}/stopAgent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agentId }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
}
