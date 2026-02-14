import { computed, ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import { unwrap } from '../api/orval'
import {
  chatChatPost,
  getChatStreamChatStreamPostUrl,
} from '../api/generated/client'
import type { ChatCitation, ChatRequest, ChatResponse } from '../api/generated/model'

const storageKey = 'paperless_chat_state'

export interface ChatMessage {
  id: string
  conversationId?: string
  question: string
  answer: string
  citations: ChatResponse['citations']
  createdAt: number
}

type PersistedChatState = {
  messages: ChatMessage[]
  conversationId: string
}

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

const isAbortError = (err: unknown) =>
  err instanceof DOMException ? err.name === 'AbortError' : err instanceof Error && err.name === 'AbortError'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const buildApiUrl = (path: string) => {
  if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) {
    const base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE
    return `${base}${path}`
  }
  const normalized = API_BASE.startsWith('/') ? API_BASE : `/${API_BASE}`
  if (path === normalized || path.startsWith(`${normalized}/`)) {
    return path
  }
  return `${normalized}${path}`
}

type ChatStreamDone = {
  answer: string
  conversation_id?: string
  citations: ChatCitation[]
}

const streamChat = async (
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
        if (line.startsWith('event:')) event = line.replace('event:', '').trim()
        if (line.startsWith('data:')) data += line.replace('data:', '').trim()
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
          const data = JSON.parse(evt.data) as { token?: string }
          if (data.token) onToken(data.token)
        } catch {
          // ignore non-json chunks
        }
      }
    }
  }
}

const loadState = (): PersistedChatState => {
  try {
    const raw = window.localStorage?.getItem(storageKey)
    if (!raw) return { messages: [], conversationId: '' }
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      return { messages: parsed, conversationId: '' }
    }
    if (parsed && typeof parsed === 'object') {
      return {
        messages: Array.isArray(parsed.messages) ? parsed.messages : [],
        conversationId: typeof parsed.conversationId === 'string' ? parsed.conversationId : '',
      }
    }
    return { messages: [], conversationId: '' }
  } catch {
    return { messages: [], conversationId: '' }
  }
}

const saveState = (state: PersistedChatState) => {
  try {
    window.localStorage?.setItem(
      storageKey,
      JSON.stringify({
        messages: state.messages.slice(0, 30),
        conversationId: state.conversationId || '',
      }),
    )
  } catch {
    // ignore
  }
}

const clampHistoryTurns = (value: number) => Math.max(1, Math.min(12, value || 6))

const buildHistory = (
  messages: ChatMessage[],
  useHistory: boolean,
  historyTurns: number,
): Array<{ question: string; answer: string }> => {
  if (!useHistory) return []
  return messages
    .slice(0, clampHistoryTurns(historyTurns))
    .map((msg) => ({ question: msg.question, answer: msg.answer }))
    .reverse()
}

const createMessage = (question: string, conversationId?: string): ChatMessage => ({
  id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  conversationId: conversationId || undefined,
  question,
  answer: '',
  citations: [],
  createdAt: Date.now(),
})

export const useChatSession = () => {
  const initialState = loadState()

  const question = ref('')
  const topK = ref(6)
  const source = ref('')
  const onlyVision = ref(false)
  const minQuality = ref(0)
  const streaming = ref(true)
  const useHistory = ref(true)
  const historyTurns = ref(6)
  const error = ref('')
  const messages = ref<ChatMessage[]>(initialState.messages)
  const conversationId = ref(initialState.conversationId)
  const activeAbort = ref<AbortController | null>(null)

  const persist = () =>
    saveState({
      messages: messages.value,
      conversationId: conversationId.value,
    })

  const stop = () => {
    if (activeAbort.value) {
      activeAbort.value.abort()
      activeAbort.value = null
    }
  }

  const askMutation = useMutation({
    mutationFn: async () => {
      const trimmedQuestion = question.value.trim()
      if (!trimmedQuestion) return
      error.value = ''
      const history = buildHistory(messages.value, useHistory.value, historyTurns.value)
      const resolvedSource = onlyVision.value ? 'vision_ocr' : source.value || undefined

      if (streaming.value) {
        const message = createMessage(trimmedQuestion, conversationId.value)
        messages.value.unshift(message)
        persist()

        const controller = new AbortController()
        activeAbort.value = controller
        question.value = ''

        await streamChat(
          {
            question: trimmedQuestion,
            top_k: topK.value,
            source: resolvedSource,
            min_quality: minQuality.value || undefined,
            history,
            conversation_id: conversationId.value || undefined,
          },
          (token) => {
            message.answer += token
          },
          (done) => {
            message.answer = done.answer || message.answer
            message.citations = done.citations ?? []
            conversationId.value = done.conversation_id || conversationId.value
            message.conversationId = conversationId.value || undefined
            persist()
          },
          (streamErr) => {
            error.value = streamErr
          },
          controller.signal,
        )
      } else {
        const data = await unwrap<ChatResponse>(
          chatChatPost({
            question: trimmedQuestion,
            top_k: topK.value,
            source: resolvedSource,
            min_quality: minQuality.value || undefined,
            history,
            conversation_id: conversationId.value || undefined,
          }),
        )
        conversationId.value = data.conversation_id || conversationId.value
        const message = createMessage(data.question, conversationId.value)
        message.answer = data.answer
        message.citations = data.citations ?? []
        messages.value.unshift(message)
        persist()
        question.value = ''
      }
    },
    onError: (err) => {
      if (!isAbortError(err)) {
        error.value = errorMessage(err, 'Chat failed')
      }
    },
    onSettled: () => {
      activeAbort.value = null
    },
  })

  const clearConversation = () => {
    messages.value = []
    conversationId.value = ''
    persist()
  }

  const newConversation = () => {
    conversationId.value = ''
    question.value = ''
    persist()
  }

  const startFollowUp = (seedQuestion: string) => {
    const seed = (seedQuestion || '').trim()
    question.value = seed ? `Follow-up on: ${seed}\n` : 'Follow-up: '
  }

  const resetControls = () => {
    question.value = ''
    topK.value = 6
    source.value = ''
    onlyVision.value = false
    minQuality.value = 0
    streaming.value = true
    useHistory.value = true
    historyTurns.value = 6
    error.value = ''
  }

  return {
    question,
    topK,
    source,
    onlyVision,
    minQuality,
    streaming,
    useHistory,
    historyTurns,
    loading: computed(() => askMutation.isPending.value),
    error,
    messages,
    conversationId,
    clearConversation,
    newConversation,
    startFollowUp,
    resetControls,
    stop,
    ask: async () => askMutation.mutateAsync(),
  }
}
