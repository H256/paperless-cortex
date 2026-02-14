import { unwrap } from '../api/orval'
import { chatChatPost, getChatStreamChatStreamPostUrl } from '../api/generated/client'
import type { ChatCitation, ChatRequest, ChatResponse } from '@/api/generated/model'

export type { ChatCitation, ChatResponse }
type ChatStreamDone = {
  answer: string
  conversation_id?: string
  citations: ChatCitation[]
}

export const sendChat = (payload: ChatRequest) => unwrap<ChatResponse>(chatChatPost(payload))

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const buildApiUrl = (path: string) => {
  if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) {
    const base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE
    return `${base}${path}`
  }
  const normalized = API_BASE.startsWith('/') ? API_BASE : `/${API_BASE}`
  return `${normalized}${path}`
}

export const streamChat = async (
  payload: ChatRequest,
  onToken: (token: string) => void,
  onDone: (data: ChatStreamDone) => void,
  onError: (message: string) => void,
  signal?: AbortSignal,
) => {
  const response = await fetch(buildApiUrl(getChatStreamChatStreamPostUrl()), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok || !response.body) {
    const text = await response.text()
    onError(text || 'Chat stream failed')
    window.dispatchEvent(
      new CustomEvent('app-error', {
        detail: { message: text || 'Chat stream failed', status: response.status },
      }),
    )
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const flushEvents = (chunk: string) => {
    const events: Array<{ event: string; data: string }> = []
    const parts = chunk.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const lines = part.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) {
          event = line.replace('event:', '').trim()
        } else if (line.startsWith('data:')) {
          data += line.replace('data:', '').trim()
        }
      }
      events.push({ event, data })
    }
    return events
  }
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = flushEvents(buffer)
    for (const evt of events) {
      if (evt.event === 'done') {
        try {
          const data = JSON.parse(evt.data) as Partial<ChatStreamDone>
          onDone({
            answer: data.answer || '',
            conversation_id: data.conversation_id || undefined,
            citations: (data.citations || []) as ChatCitation[],
          })
        } catch {
          onDone({ answer: '', citations: [] })
        }
      } else if (evt.data) {
        try {
          const data = JSON.parse(evt.data)
          if (data.token) onToken(data.token)
        } catch {
          // ignore
        }
      }
    }
  }
}
