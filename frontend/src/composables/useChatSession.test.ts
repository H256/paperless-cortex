/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

const createLocalStorageMock = () => {
  const store = new Map<string, string>()
  return {
    getItem: vi.fn((key: string) => (store.has(key) ? store.get(key) : null)),
    setItem: vi.fn((key: string, value: string) => void store.set(key, String(value))),
    removeItem: vi.fn((key: string) => void store.delete(key)),
    clear: vi.fn(() => store.clear()),
    key: vi.fn((index: number) => [...store.keys()][index] ?? null),
    get length() {
      return store.size
    },
  }
}

beforeEach(() => {
  vi.stubGlobal('localStorage', createLocalStorageMock())
})

vi.mock('../services/chatStream', () => ({
  streamChat: vi.fn(async () => undefined),
}))

const chatChatPostMock = vi.fn(
  (_payload: unknown) =>
    Promise.resolve({
      data: {
        question: 'q',
        answer: 'a',
        conversation_id: 'conv-1',
        citations: [],
      },
      status: 200,
    }),
)
vi.mock('../api/generated/client', () => ({
  chatChatPost: (payload: unknown) => chatChatPostMock(payload),
  chatFollowupsChatFollowupsPost: () => Promise.resolve({ data: { questions: [] }, status: 200 }),
}))

vi.mock('../api/orval', () => ({
  unwrap: vi.fn(async (p: Promise<{ data: unknown }>) => (await p).data),
}))

import { useChatSession } from './useChatSession'

const mountSession = async (options: Record<string, unknown> = {}) => {
  const queryClient = new QueryClient()
  const holder: { session: ReturnType<typeof useChatSession> | null } = { session: null }
  const TestHost = defineComponent({
    setup() {
      holder.session = useChatSession(options)
      return {}
    },
    render() {
      return h('div')
    },
  })
  mount(TestHost, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
    },
  })
  return holder.session!
}

// Drive one non-streaming turn so the real persist() path runs and the
// answer/conversation id are populated.
const askOneTurn = async (session: ReturnType<typeof useChatSession>) => {
  session.streaming.value = false
  session.question.value = 'what is this document about?'
  await session.ask()
}

describe('useChatSession localStorage persistence (AUDIT FE-004 / #169)', () => {
  it('does not write chat content to localStorage by default (in-memory only)', async () => {
    const session = await mountSession()
    await askOneTurn(session)

    expect(window.localStorage.setItem).not.toHaveBeenCalled()
    // The conversation is still available in memory.
    expect(session.messages.value.length).toBe(1)
    const firstMessage = session.messages.value[0]
    expect(firstMessage?.answer).toBe('a')
    expect(session.conversationId.value).toBe('conv-1')
  })

  it('does not restore a previously stored conversation by default', async () => {
    window.localStorage.setItem(
      'paperless_chat_state',
      JSON.stringify({
        messages: [{ question: 'old', answer: 'old-answer', citations: [] }],
        conversationId: 'old-conv',
      }),
    )
    const session = await mountSession()

    // Not restored: default is in-memory only (nothing read from storage).
    expect(session.messages.value.length).toBe(0)
    expect(session.conversationId.value).toBe('')
    expect(window.localStorage.getItem).not.toHaveBeenCalled()
    // A new turn writes nothing to storage.
    vi.mocked(window.localStorage.setItem).mockClear()
    await askOneTurn(session)
    expect(window.localStorage.setItem).not.toHaveBeenCalled()
  })

  it('persists to localStorage only when persist: true is explicitly set', async () => {
    const session = await mountSession({ persist: true, storageKey: 'paperless_chat_state' })
    await askOneTurn(session)

    expect(window.localStorage.setItem).toHaveBeenCalled()
    const call = vi.mocked(window.localStorage.setItem).mock.calls[0]
    expect(call?.[0]).toBe('paperless_chat_state')
    const parsed = JSON.parse(String(call?.[1]))
    expect(parsed.conversationId).toBe('conv-1')
    expect(Array.isArray(parsed.messages)).toBe(true)
    expect((parsed.messages[0] as { answer?: string })?.answer).toBe('a')
  })
})
