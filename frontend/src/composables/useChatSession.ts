import { computed, ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import { unwrap } from '../api/orval'
import {
  chatChatPost,
  chatFollowupsChatFollowupsPost,
} from '../api/generated/client'
import type { ChatFollowupsResponse, ChatResponse } from '../api/generated/model'
import { streamChat } from '../services/chatStream'
import type { ChatFollowupsRequest } from '../api/generated/model'

type UseChatSessionOptions = {
  storageKey?: string
  defaultDocId?: number | null
  defaultDocScope?: boolean
  defaultRelationshipMode?: 'none' | 'chrono'
}

export interface ChatMessage {
  id: string
  conversationId?: string
  question: string
  answer: string
  citations: ChatResponse['citations']
  followups?: string[]
  followupsLoading?: boolean
  followupsError?: string
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

const normalizeFollowups = (values: unknown): string[] => {
  if (!Array.isArray(values)) return []
  return values.map((value) => String(value).trim()).filter(Boolean)
}

const loadState = (storageKey: string): PersistedChatState => {
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

const saveState = (storageKey: string, state: PersistedChatState) => {
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
  followups: [],
  followupsLoading: false,
  followupsError: '',
  createdAt: Date.now(),
})

export const useChatSession = (options: UseChatSessionOptions = {}) => {
  const storageKey = options.storageKey || 'paperless_chat_state'
  const initialState = loadState(storageKey)

  const question = ref('')
  const topK = ref(6)
  const source = ref('')
  const onlyVision = ref(false)
  const minQuality = ref(0)
  const streaming = ref(true)
  const useHistory = ref(true)
  const historyTurns = ref(6)
  const docScope = ref(Boolean(options.defaultDocScope))
  const docId = ref<number | null>(options.defaultDocId ?? null)
  const relationshipMode = ref<'none' | 'chrono'>(options.defaultRelationshipMode ?? 'none')
  const error = ref('')
  const messages = ref<ChatMessage[]>(initialState.messages)
  const conversationId = ref(initialState.conversationId)
  const activeAbort = ref<AbortController | null>(null)

  const persist = () =>
    saveState(storageKey, {
      messages: messages.value,
      conversationId: conversationId.value,
    })

  const followupsMutation = useMutation({
    mutationFn: (payload: ChatFollowupsRequest) =>
      unwrap<ChatFollowupsResponse>(chatFollowupsChatFollowupsPost(payload)),
  })

  const fetchFollowupsForMessage = async (message: ChatMessage, payload: ChatFollowupsRequest) => {
    message.followupsLoading = true
    message.followupsError = ''
    try {
      const data = await followupsMutation.mutateAsync(payload)
      message.followups = normalizeFollowups(data.questions)
    } catch (err: unknown) {
      message.followupsError = errorMessage(err, 'Failed to load follow-ups')
    } finally {
      message.followupsLoading = false
      persist()
    }
  }

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
      const resolvedDocId = docScope.value && typeof docId.value === 'number' ? docId.value : undefined
      const relationship_mode = relationshipMode.value !== 'none' ? relationshipMode.value : undefined
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
            doc_id: resolvedDocId,
            relationship_mode,
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
            void fetchFollowupsForMessage(message, {
              question: message.question,
              answer: message.answer,
              citations: message.citations || [],
              doc_id: resolvedDocId,
              relationship_mode,
            })
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
            doc_id: resolvedDocId,
            relationship_mode,
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
        void fetchFollowupsForMessage(message, {
          question: message.question,
          answer: message.answer,
          citations: message.citations || [],
          doc_id: resolvedDocId,
          relationship_mode,
        })
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
    docScope.value = Boolean(options.defaultDocScope)
    relationshipMode.value = options.defaultRelationshipMode ?? 'none'
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
    docScope,
    docId,
    relationshipMode,
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
