export type AgreementField = 'title' | 'date' | 'correspondent'

export type AgreementInput = {
  /** Suggested value per source key, e.g. `vision_ocr`, `paperless_ocr`, `similar_docs`. */
  values: Record<string, unknown>
  /** Values found in the document text without AI (dates or correspondent names). */
  textValues?: string[]
}

export type AgreementResult = {
  /** Number of sources (incl. the text) that carry a value. */
  total: number
  /** Per source key: how many sources, including itself, carry the same value. */
  agreeing: Record<string, number>
  /** Whether the text candidates contain the same value, per source key. */
  textMatches: Record<string, boolean>
}

const collapse = (value: string) =>
  value
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[.,;:!"'`´]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()

/** Comparable form of a suggestion value; dates compare by their ISO day. */
export const normalizeAgreementValue = (field: AgreementField, value: unknown): string => {
  if (typeof value !== 'string') return ''
  const text = value.trim()
  if (!text) return ''
  if (field === 'date') {
    const iso = text.match(/^(\d{4}-\d{2}-\d{2})/)
    if (iso) return iso[1] as string
    const german = text.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/)
    if (german) {
      const [, day, month, year] = german
      return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    }
    return text
  }
  return collapse(text)
}

export const computeAgreement = (field: AgreementField, input: AgreementInput): AgreementResult => {
  const normalizedBySource: Record<string, string> = {}
  for (const [source, value] of Object.entries(input.values)) {
    const normalized = normalizeAgreementValue(field, value)
    if (normalized) normalizedBySource[source] = normalized
  }
  const textNormalized = new Set(
    (input.textValues ?? [])
      .map((value) => normalizeAgreementValue(field, value))
      .filter((value) => Boolean(value)),
  )

  const sources = Object.keys(normalizedBySource)
  const agreeing: Record<string, number> = {}
  const textMatches: Record<string, boolean> = {}
  for (const source of sources) {
    const mine = normalizedBySource[source] as string
    const sameSources = sources.filter((other) => normalizedBySource[other] === mine).length
    const matchesText = textNormalized.has(mine)
    textMatches[source] = matchesText
    agreeing[source] = sameSources + (matchesText ? 1 : 0)
  }
  return {
    total: sources.length + (textNormalized.size > 0 ? 1 : 0),
    agreeing,
    textMatches,
  }
}
