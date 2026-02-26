import { describe, expect, it, vi } from 'vitest'

const toStream = (chunks: string[]) =>
  new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })

describe('streamChat', () => {
  const loadStreamChat = async () => {
    const module = await import('./chatStream')
    return module.streamChat
  }

  it('builds API URL for non-/api path variants', async () => {
    vi.resetModules()
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => new Response('ok', { status: 400 }))
    vi.stubGlobal('fetch', fetchMock)

    await streamChat(
      { question: 'q' },
      () => undefined,
      () => undefined,
      () => undefined,
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/chat/stream',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('builds API URL for absolute base URLs', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_API_BASE_URL', 'https://example.local/api/')
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => new Response('ok', { status: 400 }))
    vi.stubGlobal('fetch', fetchMock)

    await streamChat(
      { question: 'q' },
      () => undefined,
      () => undefined,
      () => undefined,
    )
    expect(fetchMock).toHaveBeenCalledWith(
      'https://example.local/api/chat/stream',
      expect.objectContaining({ method: 'POST' }),
    )
    vi.unstubAllEnvs()
  })

  it('emits token and done payloads from SSE chunks', async () => {
    vi.resetModules()
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/api/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => {
      const body = toStream([
        'data: {"token":"Hello"}\n\n',
        'data: {"token":" world"}\n\n',
        'event: done\ndata: {"answer":"Hello world","conversation_id":"abc","citations":[]}\n\n',
      ])
      return new Response(body, { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const tokens: string[] = []
    const doneEvents: unknown[] = []
    const errors: string[] = []

    await streamChat(
      { question: 'q' },
      (token) => tokens.push(token),
      (done) => doneEvents.push(done),
      (err) => errors.push(err),
    )

    expect(tokens).toEqual(['Hello', ' world'])
    expect(doneEvents).toEqual([
      { answer: 'Hello world', conversation_id: 'abc', citations: [] },
    ])
    expect(errors).toEqual([])
  })

  it('handles malformed done payload gracefully', async () => {
    vi.resetModules()
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/api/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => {
      const body = toStream([
        'data: {"token":"ignored"}\n\n',
        'event: done\ndata: not-json\n\n',
      ])
      return new Response(body, { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const doneEvents: unknown[] = []

    await streamChat(
      { question: 'q2' },
      () => undefined,
      (done) => doneEvents.push(done),
      () => undefined,
    )

    expect(doneEvents).toEqual([{ answer: '', citations: [] }])
  })

  it('reports error text when stream endpoint fails', async () => {
    vi.resetModules()
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/api/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => new Response('bad request', { status: 400 }))
    vi.stubGlobal('fetch', fetchMock)

    const errors: string[] = []
    await streamChat(
      { question: 'q3' },
      () => undefined,
      () => undefined,
      (err) => errors.push(err),
    )
    expect(errors).toEqual(['bad request'])
  })

  it('ignores malformed token chunks without calling onError', async () => {
    vi.resetModules()
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/api/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => {
      const body = toStream([
        'data: not-json\n\n',
        'event: done\ndata: {"answer":"ok","citations":[]}\n\n',
      ])
      return new Response(body, { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const errors: string[] = []
    const doneEvents: unknown[] = []
    await streamChat(
      { question: 'q4' },
      () => undefined,
      (done) => doneEvents.push(done),
      (err) => errors.push(err),
    )

    expect(doneEvents).toEqual([{ answer: 'ok', conversation_id: undefined, citations: [] }])
    expect(errors).toEqual([])
  })

  it('falls back to collected tokens when done event is missing', async () => {
    vi.resetModules()
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/api/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => {
      const body = toStream([
        'data: {"token":"Hello"}\n\n',
        'data: {"token":" world"}\n\n',
      ])
      return new Response(body, { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const doneEvents: unknown[] = []
    const errors: string[] = []
    await streamChat(
      { question: 'q5' },
      () => undefined,
      (done) => doneEvents.push(done),
      (err) => errors.push(err),
    )

    expect(doneEvents).toEqual([{ answer: 'Hello world', citations: [] }])
    expect(errors).toEqual([])
  })

  it('reports an error when stream ends without tokens and without done event', async () => {
    vi.resetModules()
    vi.doMock('../api/generated/client', () => ({
      getChatStreamChatStreamPostUrl: () => '/api/chat/stream',
    }))
    const streamChat = await loadStreamChat()

    const fetchMock = vi.fn(async () => new Response(toStream([]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const errors: string[] = []
    await streamChat(
      { question: 'q6' },
      () => undefined,
      () => undefined,
      (err) => errors.push(err),
    )

    expect(errors).toEqual(['Chat stream ended unexpectedly. Try disabling streaming.'])
  })
})
