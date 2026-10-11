export class ApiError extends Error {
  status: number
  detail?: string
  error_code?: string

  constructor(message: string, status: number, detail?: string, error_code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.error_code = error_code
  }
}

/**
 * Extract a human-readable detail from a backend error body.
 * FastAPI returns `{ detail: string | object | string[] }`; some endpoints
 * also surface an `error_code`. Returns undefined when nothing usable exists.
 */
export const extractDetail = (value: unknown): string | undefined => {
  if (!value || typeof value !== 'object') return undefined
  const detail = (value as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return JSON.stringify(detail)
  return undefined
}

export const extractErrorCode = (value: unknown): string | undefined => {
  if (!value || typeof value !== 'object') return undefined
  const code = (value as { error_code?: unknown }).error_code
  return typeof code === 'string' ? code : undefined
}

const RETRYABLE_METHODS = new Set(['GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS'])
const RETRYABLE_STATUS = new Set([409, 503])

const isRetryableError = (error: unknown): boolean => {
  if (error instanceof TypeError) return true // fetch network failure
  // AbortSignal.timeout() rejects with a TimeoutError; an intentional abort
  // (AbortError) is not retried.
  return error instanceof DOMException && error.name === 'TimeoutError'
}

export interface RequestOptions extends RequestInit {
  /**
   * Number of retries (in addition to the initial attempt) for idempotent
   * methods (GET/HEAD/PUT/DELETE/OPTIONS) on 409/503 or network/timeout
   * failures. Defaults to 0 (no retry). Non-idempotent methods (POST/PATCH)
   * are never retried automatically.
   */
  retry?: number
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Central JSON request client. All hand-written API calls should route
 * through here so error normalization and retry policy live in one place.
 *
 * On a non-2xx response (or network/timeout failure) throws a normalized
 * `ApiError` carrying `status`, `detail`, and `error_code`.
 */
export const requestJson = async <T>(input: string, init: RequestOptions = {}): Promise<T> => {
  const { retry = 0, ...requestInit } = init
  const method = (requestInit.method || 'GET').toUpperCase()
  const idempotent = RETRYABLE_METHODS.has(method)
  const maxAttempts = 1 + (idempotent ? Math.max(0, retry) : 0)

  let lastError: unknown
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    let response: Response
    try {
      response = await fetch(input, requestInit)
    } catch (error) {
      lastError = error
      if (idempotent && attempt < maxAttempts - 1 && isRetryableError(error)) {
        await delay(100 * (attempt + 1))
        continue
      }
      throw new ApiError(`Network error: ${String(error)}`, 0, undefined, undefined)
    }

    const body = await response.text()
    const parsed = body ? (JSON.parse(body) as Record<string, unknown>) : {}

    if (response.ok) {
      return parsed as T
    }

    const detail = extractDetail(parsed)
    const errorCode = extractErrorCode(parsed)
    const message = detail || `Request failed (${response.status})`

    if (idempotent && attempt < maxAttempts - 1 && RETRYABLE_STATUS.has(response.status)) {
      await delay(100 * (attempt + 1))
      continue
    }

    throw new ApiError(message, response.status, detail, errorCode)
  }

  throw new ApiError(`Network error: ${String(lastError)}`, 0, undefined, undefined)
}