import type { LocationQuery } from 'vue-router'
import { formatDateTime } from './dateTime'

export type BBox = [number, number, number, number]

export const parseBBox = (value: unknown): BBox | null => {
  if (!value) return null
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'string') return null
  const parts = raw.split(',').map((part) => Number(part.trim()))
  if (parts.length !== 4 || parts.some((v) => Number.isNaN(v))) return null
  return parts as BBox
}

export const toTitle = (value: string | null | undefined) => {
  if (!value) return 'Unknown'
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export const formatDocDate = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language).format(parsed)
}

export const compactErrorMessage = (message?: string | null) => {
  if (!message) return ''
  const normalized = message.replace(/\s+/g, ' ').trim()
  if (normalized.length <= 90) return normalized
  return `${normalized.slice(0, 87)}...`
}

export const embeddingTelemetryLabel = (checkpoint?: Record<string, unknown> | null) => {
  if (!checkpoint || typeof checkpoint !== 'object') return ''
  const splitChunks = typeof checkpoint.split_chunks === 'number' ? checkpoint.split_chunks : null
  const overflowCalls =
    typeof checkpoint.overflow_fallback_calls === 'number' ? checkpoint.overflow_fallback_calls : null
  if ((splitChunks ?? 0) <= 0 && (overflowCalls ?? 0) <= 0) return ''
  const parts: string[] = []
  if ((splitChunks ?? 0) > 0) parts.push(`split chunks: ${splitChunks}`)
  if ((overflowCalls ?? 0) > 0) parts.push(`fallback calls: ${overflowCalls}`)
  return parts.join(' | ')
}

export const toDateTime = (value?: string | null) => {
  if (!value) return '-'
  return formatDateTime(value) || value
}

export const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

export const queryToRecord = (query: LocationQuery, excludeKeys: string[] = []): Record<string, string> => {
  const excluded = new Set(excludeKeys)
  const nextQuery: Record<string, string> = {}
  Object.entries(query).forEach(([key, val]) => {
    if (excluded.has(key) || val === undefined || val === null) return
    const entry = Array.isArray(val) ? val[0] : val
    if (typeof entry === 'string') nextQuery[key] = entry
  })
  return nextQuery
}
