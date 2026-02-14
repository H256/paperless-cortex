import type { LocationQuery } from 'vue-router'

export const queryString = (value: unknown, fallback = ''): string => {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' ? raw : fallback
}

export const queryBool = (value: unknown, fallback: boolean): boolean => {
  const raw = Array.isArray(value) ? value[0] : value
  if (raw === '1' || raw === 'true') return true
  if (raw === '0' || raw === 'false') return false
  return fallback
}

export const queryNumber = (value: unknown, fallback: number): number => {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : fallback
}

export const isSameQueryState = (current: LocationQuery, next: Record<string, string>): boolean => {
  const keys = new Set<string>([...Object.keys(current), ...Object.keys(next)])
  for (const key of keys) {
    const currRaw = current[key]
    const curr = Array.isArray(currRaw) ? currRaw[0] : currRaw
    if (String(curr || '') !== String(next[key] || '')) {
      return false
    }
  }
  return true
}

