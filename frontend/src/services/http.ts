type QueryParams = Record<string, string | number | boolean | null | undefined>

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status: number, detail?: string) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const resolveBase = () => {
  if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) return API_BASE
  const normalized = API_BASE.startsWith('/') ? API_BASE : `/${API_BASE}`
  return `${window.location.origin}${normalized}`
}

const buildUrl = (path: string, params?: QueryParams) => {
  const base = resolveBase()
  const baseIsAbsolute = API_BASE.startsWith('http://') || API_BASE.startsWith('https://')
  const normalizedBase = base.endsWith('/') ? base : `${base}/`
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path
  const url = new URL(normalizedPath, normalizedBase)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return
      url.searchParams.set(key, String(value))
    })
  }
  if (baseIsAbsolute) {
    return url.toString()
  }
  return `${url.pathname}${url.search}`
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  params?: QueryParams
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
}

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

export const request = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const { method = 'GET', params, body, headers, signal } = options
  const url = buildUrl(path, params)
  const init: RequestInit = {
    method,
    headers: {
      ...headers,
    },
    signal,
  }
  if (body !== undefined) {
    init.headers = {
      'Content-Type': 'application/json',
      ...headers,
    }
    init.body = JSON.stringify(body)
  }
  let response: Response
  try {
    response = await fetch(url, init)
  } catch (err: unknown) {
    const message = errorMessage(err, 'Network error')
    window.dispatchEvent(new CustomEvent('app-error', { detail: { message, status: 0 } }))
    throw err instanceof Error ? err : new Error(message)
  }
  if (!response.ok) {
    let message = response.statusText || 'Request failed'
    let detail: string | undefined
    try {
      const data = await response.json()
      detail = data?.detail || data?.message
      if (detail) message = detail
    } catch {
      try {
        const text = await response.text()
        if (text) message = text
      } catch {
        // ignore
      }
    }
    window.dispatchEvent(
      new CustomEvent('app-error', { detail: { message, status: response.status, detail } }),
    )
    throw new ApiError(message, response.status, detail)
  }
  if (response.status === 204) return undefined as T
  const text = await response.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}
