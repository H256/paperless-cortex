import { ApiError } from '../services/http'

type OrvalResponse<T> = { data: T; status: number; headers: Headers }

const notifyError = (message: string, detail?: string, status?: number) => {
  console.warn('API error', { message, detail, status })
  window.dispatchEvent(new CustomEvent('app-error', { detail: { message, detail, status } }))
}

export const unwrap = async <T, E = { detail?: string }>(
  promise: Promise<OrvalResponse<T | E>>,
): Promise<T> => {
  const res = await promise
  if (res.status >= 200 && res.status < 300) {
    return res.data
  }
  const detail = (res.data as { detail?: string } | null | undefined)?.detail
  const message = detail || `Request failed (${res.status})`
  notifyError(message, detail, res.status)
  throw new ApiError(message, res.status, detail)
}
