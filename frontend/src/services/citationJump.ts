type CitationJumpPayload = {
  docId: number
  page?: number
  bbox?: string
  source?: string
  snippet?: string
  createdAt: number
}

const JUMP_STORAGE_PREFIX = 'paperless_citation_jump:'
const JUMP_TTL_MS = 1000 * 60 * 30

const toNumber = (value: unknown): number | null => {
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return n
}

const parseBBoxString = (value: string): string | undefined => {
  const numbers = value
    .split(',')
    .map((part) => Number(part.trim()))
    .filter((part) => Number.isFinite(part))
  if (numbers.length !== 4) return undefined
  return numbers.map((part) => part.toFixed(5)).join(',')
}

const toBBoxString = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    return parseBBoxString(value)
  }
  if (!Array.isArray(value) || value.length !== 4) return undefined
  const numbers = value.map((part) => Number(part))
  if (numbers.some((part) => Number.isNaN(part))) return undefined
  return numbers.map((part) => part.toFixed(5)).join(',')
}

const createJumpToken = (): string => {
  const rand = Math.random().toString(36).slice(2, 10)
  return `${Date.now().toString(36)}-${rand}`
}

const writeJumpPayload = (payload: CitationJumpPayload): string | null => {
  try {
    pruneCitationJumps()
    const token = createJumpToken()
    window.sessionStorage.setItem(`${JUMP_STORAGE_PREFIX}${token}`, JSON.stringify(payload))
    return token
  } catch {
    return null
  }
}

const pruneCitationJumps = () => {
  try {
    const now = Date.now()
    const removeKeys: string[] = []
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const key = window.sessionStorage.key(i)
      if (!key || !key.startsWith(JUMP_STORAGE_PREFIX)) continue
      const raw = window.sessionStorage.getItem(key)
      if (!raw) {
        removeKeys.push(key)
        continue
      }
      try {
        const parsed = JSON.parse(raw) as CitationJumpPayload
        const createdAt = Number(parsed?.createdAt || 0)
        if (!createdAt || now - createdAt > JUMP_TTL_MS) {
          removeKeys.push(key)
        }
      } catch {
        removeKeys.push(key)
      }
    }
    removeKeys.forEach((key) => window.sessionStorage.removeItem(key))
  } catch {
    // ignore storage errors
  }
}

export const buildDocumentCitationLink = (input: {
  docId: unknown
  page?: unknown
  bbox?: unknown
  source?: unknown
  snippet?: unknown
}): string => {
  const docId = toNumber(input.docId)
  if (docId === null || docId <= 0) return ''

  const page = toNumber(input.page)
  const bbox = toBBoxString(input.bbox)
  const payload: CitationJumpPayload = {
    docId,
    createdAt: Date.now(),
  }
  if (page !== null && page > 0) payload.page = Math.floor(page)
  if (bbox) payload.bbox = bbox
  if (typeof input.source === 'string' && input.source.trim()) payload.source = input.source.trim()
  if (typeof input.snippet === 'string' && input.snippet.trim()) payload.snippet = input.snippet.trim()

  const params = new URLSearchParams()
  if (payload.page) params.set('page', String(payload.page))
  if (payload.bbox) params.set('bbox', payload.bbox)

  const jumpToken = writeJumpPayload(payload)
  if (jumpToken) params.set('jump', jumpToken)

  const query = params.toString()
  return query ? `/documents/${docId}?${query}` : `/documents/${docId}`
}

export const consumeCitationJump = (jumpQueryValue: unknown): { page?: number; bbox?: string } | null => {
  const raw = Array.isArray(jumpQueryValue) ? jumpQueryValue[0] : jumpQueryValue
  if (typeof raw !== 'string' || !raw.trim()) return null
  const token = raw.trim()
  const key = `${JUMP_STORAGE_PREFIX}${token}`
  try {
    const stored = window.sessionStorage.getItem(key)
    window.sessionStorage.removeItem(key)
    if (!stored) return null
    const parsed = JSON.parse(stored) as CitationJumpPayload
    if (!parsed || typeof parsed !== 'object') return null
    if (Date.now() - Number(parsed.createdAt || 0) > JUMP_TTL_MS) return null
    const result: { page?: number; bbox?: string } = {}
    if (typeof parsed.page === 'number' && parsed.page > 0) result.page = parsed.page
    if (typeof parsed.bbox === 'string' && parsed.bbox.trim()) result.bbox = parsed.bbox.trim()
    return result
  } catch {
    return null
  }
}
