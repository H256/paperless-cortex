import { defineStore } from 'pinia'
import { sendChat, type ChatResponse, streamChat } from '../services/chat'

const storageKey = 'paperless_chat_history'
const loadMessages = (): ChatMessage[] => {
  try {
    const raw = window.localStorage?.getItem(storageKey)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}
const saveMessages = (messages: ChatMessage[]) => {
  try {
    window.localStorage?.setItem(storageKey, JSON.stringify(messages.slice(0, 30)))
  } catch {
    // ignore
  }
}

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
    loading: false,
    error: '',
    messages: loadMessages(),
    activeAbort: null as AbortController | null,
  }),
  actions: {
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
        const history = this.messages
          .slice(0, 4)
          .map((msg) => ({ question: msg.question, answer: msg.answer }))
          .reverse()
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
          saveMessages(this.messages)
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
            },
            (token) => {
              message.answer += token
            },
            (done) => {
              message.answer = done.answer || message.answer
              message.citations = done.citations ?? []
              saveMessages(this.messages)
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
          })
          this.messages.unshift({
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            question: data.question,
            answer: data.answer,
            citations: data.citations ?? [],
            createdAt: Date.now(),
          })
          saveMessages(this.messages)
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
