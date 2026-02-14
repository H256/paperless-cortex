import { defineStore } from 'pinia'
import { sendChat, type ChatResponse, streamChat } from '../services/chat'

const storageKey = 'paperless_chat_state'

type PersistedChatState = {
  messages: ChatMessage[]
  conversationId: string
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

const initialState = loadState()

export interface ChatMessage {
  id: string
  question: string
  answer: string
  citations: ChatResponse['citations']
  createdAt: number
}

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

const isAbortError = (err: unknown) =>
  err instanceof DOMException ? err.name === 'AbortError' : err instanceof Error && err.name === 'AbortError'

export const useChatStore = defineStore('chat', {
  state: () => ({
    question: '',
    topK: 6,
    source: '',
    onlyVision: false,
    minQuality: 0,
    streaming: true,
    useHistory: true,
    historyTurns: 6,
    loading: false,
    error: '',
    messages: initialState.messages,
    conversationId: initialState.conversationId,
    activeAbort: null as AbortController | null,
  }),
  actions: {
    clearConversation() {
      this.messages = []
      this.conversationId = ''
      saveState({ messages: this.messages, conversationId: this.conversationId })
    },
    startFollowUp(seedQuestion: string) {
      const seed = (seedQuestion || '').trim()
      this.question = seed ? `Follow-up on: ${seed}\n` : 'Follow-up: '
    },
    stop() {
      if (this.activeAbort) {
        this.activeAbort.abort()
        this.activeAbort = null
        this.loading = false
      }
    },
    async ask() {
      if (!this.question) return
      if (this.loading) {
        this.stop()
      }
      this.loading = true
      this.error = ''
      try {
        const history = this.useHistory
          ? this.messages
              .slice(0, Math.max(1, Math.min(12, this.historyTurns || 6)))
              .map((msg) => ({ question: msg.question, answer: msg.answer }))
              .reverse()
          : []
        const source = this.onlyVision ? 'vision_ocr' : this.source || undefined
        if (this.streaming) {
          const message: ChatMessage = {
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            question: this.question,
            answer: '',
            citations: [],
            createdAt: Date.now(),
          }
          this.messages.unshift(message)
          saveState({ messages: this.messages, conversationId: this.conversationId })
          const controller = new AbortController()
          this.activeAbort = controller
          const questionText = this.question
          this.question = ''
          await streamChat(
            {
              question: questionText,
              top_k: this.topK,
              source,
              min_quality: this.minQuality || undefined,
              history,
              conversation_id: this.conversationId || undefined,
            },
            (token) => {
              message.answer += token
            },
            (done) => {
              message.answer = done.answer || message.answer
              message.citations = done.citations ?? []
              this.conversationId = done.conversation_id || this.conversationId
              saveState({ messages: this.messages, conversationId: this.conversationId })
            },
            (err) => {
              this.error = err
            },
            controller.signal,
          )
        } else {
          const data = await sendChat({
            question: this.question,
            top_k: this.topK,
            source,
            min_quality: this.minQuality || undefined,
            history,
            conversation_id: this.conversationId || undefined,
          })
          this.conversationId = data.conversation_id || this.conversationId
          this.messages.unshift({
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            question: data.question,
            answer: data.answer,
            citations: data.citations ?? [],
            createdAt: Date.now(),
          })
          saveState({ messages: this.messages, conversationId: this.conversationId })
          this.question = ''
        }
      } catch (err: unknown) {
        if (!isAbortError(err)) {
          this.error = errorMessage(err, 'Chat failed')
        }
      } finally {
        this.loading = false
        this.activeAbort = null
      }
    },
  },
})
