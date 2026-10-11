import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, extractDetail, extractErrorCode, requestJson } from './http'

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('extractDetail', () => {
  it('returns string detail', () => {
    expect(extractDetail({ detail: 'boom' })).toBe('boom')
  })
  it('stringifies array detail', () => {
    expect(extractDetail({ detail: ['a', 'b'] })).toBe('["a","b"]')
  })
  it('returns undefined for non-object or missing detail', () => {
    expect(extractDetail(null)).toBeUndefined()
    expect(extractDetail('text')).toBeUndefined()
    expect(extractDetail({})).toBeUndefined()
  })
})

describe('extractErrorCode', () => {
  it('returns string error_code', () => {
    expect(extractErrorCode({ error_code: 'E_TIMEOUT' })).toBe('E_TIMEOUT')
  })
  it('returns undefined when absent', () => {
    expect(extractErrorCode({})).toBeUndefined()
    expect(extractErrorCode({ error_code: 5 })).toBeUndefined()
  })
})

describe('requestJson', () => {
  it('returns parsed body on 2xx', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true, n: 1 }))
    vi.stubGlobal('fetch', fetchMock)
    const result = await requestJson<{ ok: boolean; n: number }>('/api/x')
    expect(result).toEqual({ ok: true, n: 1 })
  })

  it('returns {} for empty body on 2xx', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 200 })))
    const result = await requestJson<Record<string, unknown>>('/api/x', { method: 'DELETE' })
    expect(result).toEqual({})
  })

  it('throws normalized ApiError with detail on 4xx', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(404, { detail: 'not found' })))
    await expect(requestJson('/api/x')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      detail: 'not found',
      message: 'not found',
    })
  })

  it('throws normalized ApiError on 5xx with fallback message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(500, {})))
    await expect(requestJson('/api/x')).rejects.toMatchObject({
      status: 500,
      message: 'Request failed (500)',
    })
  })

  it('carries error_code when present', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(422, { detail: 'bad', error_code: 'E_VALIDATION' })),
    )
    await expect(requestJson('/api/x')).rejects.toMatchObject({
      status: 422,
      detail: 'bad',
      error_code: 'E_VALIDATION',
    })
  })

  it('throws ApiError(status=0) on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('fetch failed')
    }))
    await expect(requestJson('/api/x')).rejects.toMatchObject({
      status: 0,
      message: 'Network error: TypeError: fetch failed',
    })
  })

  it('retries idempotent GET on 503 then succeeds', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(503, { detail: 'unavailable' }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    const result = await requestJson<{ ok: boolean }>('/api/x', { retry: 1 })
    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('retries idempotent GET on network error then succeeds', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('fetch failed'))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    const result = await requestJson<{ ok: boolean }>('/api/x', { retry: 1 })
    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('retries idempotent GET on timeout then succeeds', async () => {
    const timeout = new DOMException('signal timed out', 'TimeoutError')
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(timeout)
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    const result = await requestJson<{ ok: boolean }>('/api/x', { retry: 1 })
    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not retry an intentional abort', async () => {
    const fetchMock = vi.fn(async () => {
      throw new DOMException('aborted', 'AbortError')
    })
    vi.stubGlobal('fetch', fetchMock)
    await expect(requestJson('/api/x', { retry: 3 })).rejects.toMatchObject({ status: 0 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not retry non-idempotent POST', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(503, { detail: 'unavailable' }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(requestJson('/api/x', { method: 'POST', body: '{}', retry: 3 })).rejects.toBeInstanceOf(
      ApiError,
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('gives up after the retry budget and throws the last status', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(503, { detail: 'unavailable' }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(requestJson('/api/x', { retry: 2 })).rejects.toMatchObject({ status: 503 })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})
