import type { WritebackDryRunItem } from '../services/writeback'

type WritebackFieldValueSide = 'original' | 'proposed'

export const rowsForWritebackItem = (item: WritebackDryRunItem) => [
  item.title,
  item.document_date,
  item.correspondent,
  item.tags,
  item.note,
]

export const writebackFieldLabel = (field: string) => {
  if (field === 'issue_date' || field === 'document_date') return 'Issue date'
  if (field === 'correspondent') return 'Correspondent'
  if (field === 'title') return 'Title'
  if (field === 'tags') return 'Tags'
  if (field === 'note') return 'Note'
  return field
}

const noteText = (value: unknown) => {
  if (!value || typeof value !== 'object') return ''
  const text = (value as { text?: unknown }).text
  return typeof text === 'string' ? text : ''
}

export const writebackDisplayValue = (
  field: string,
  value: unknown,
  changed: boolean,
  side: WritebackFieldValueSide,
) => {
  if (side === 'proposed' && !changed) return ''
  if (value === null || value === undefined || value === '') return '-'

  if (field === 'correspondent' && typeof value === 'object' && value !== null) {
    const v = value as { name?: unknown; id?: unknown }
    const name = typeof v.name === 'string' ? v.name : ''
    const id = typeof v.id === 'number' ? v.id : null
    if (name && id !== null) return `${name} (#${id})`
    if (name) return name
    if (id !== null) return `#${id}`
    return '-'
  }

  if (field === 'tags' && typeof value === 'object' && value !== null) {
    const v = value as { names?: unknown; ids?: unknown }
    const names = Array.isArray(v.names)
      ? v.names.map((entry) => String(entry).trim()).filter(Boolean)
      : []
    if (names.length) return names.join(', ')
    const ids = Array.isArray(v.ids) ? v.ids.map((entry) => String(entry).trim()).filter(Boolean) : []
    return ids.length ? ids.join(', ') : '-'
  }

  if (field === 'note') {
    if (typeof value === 'string') return value
    const extracted = noteText(value)
    if (extracted) return extracted
    if (typeof value === 'object' && value !== null) return '-'
  }

  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}
