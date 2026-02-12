import { ApiError } from '../services/http'

type OrvalLikeResponse = { data: unknown; status: number }

const notifyError = (message: string, detail?: string, status?: number) => {
  console.warn('API error', { message, detail, status })
  window.dispatchEvent(new CustomEvent('app-error', { detail: { message, detail, status } }))
}

const extractDetail = (value: unknown): string | undefined => {
  if (!value || typeof value !== 'object') return undefined
  const detail = (value as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return JSON.stringify(detail)
  return undefined
}

export const unwrap = async <T>(promise: Promise<OrvalLikeResponse>): Promise<T> => {
  const res = await promise
  if (res.status >= 200 && res.status < 300) {
    return res.data as T
  }
  const detail = extractDetail(res.data)
  const message = detail || `Request failed (${res.status})`
  notifyError(message, detail, res.status)
  throw new ApiError(message, res.status, detail)
}
