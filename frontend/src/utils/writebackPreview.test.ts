import { describe, expect, it } from 'vitest'
import { rowsForWritebackItem, writebackDisplayValue, writebackFieldLabel } from './writebackPreview'

describe('writebackPreview utils', () => {
  const item = {
    title: { field: 'title', original: 'A', proposed: 'B', changed: true },
    document_date: { field: 'issue_date', original: '2026-01-01', proposed: '2026-02-01', changed: true },
    correspondent: {
      field: 'correspondent',
      original: { id: 1, name: 'Old' },
      proposed: { id: 2, name: 'New' },
      changed: true,
    },
    tags: {
      field: 'tags',
      original: { ids: [1], names: ['x'] },
      proposed: { ids: [1, 2], names: ['x', 'y'] },
      changed: true,
    },
    note: { field: 'note', original: { id: 1, text: 'old' }, proposed: { text: 'new' }, changed: true },
  } as const

  it('returns rows in expected order', () => {
    const rows = rowsForWritebackItem(item as never)
    expect(rows).toHaveLength(5)
    expect(rows[0]!.field).toBe('title')
    expect(rows[4]!.field).toBe('note')
  })

  it('formats field labels', () => {
    expect(writebackFieldLabel('issue_date')).toBe('Issue date')
    expect(writebackFieldLabel('correspondent')).toBe('Correspondent')
    expect(writebackFieldLabel('custom')).toBe('custom')
  })

  it('formats correspondent/tags/note values', () => {
    expect(writebackDisplayValue('correspondent', { id: 3, name: 'ACME' }, true, 'proposed')).toBe('ACME (#3)')
    expect(writebackDisplayValue('tags', { names: ['a', 'b'] }, true, 'proposed')).toBe('a, b')
    expect(writebackDisplayValue('note', { text: 'hello' }, true, 'proposed')).toBe('hello')
  })

  it('hides unchanged proposed values and handles empty values', () => {
    expect(writebackDisplayValue('title', 'unchanged', false, 'proposed')).toBe('')
    expect(writebackDisplayValue('title', '', true, 'original')).toBe('-')
  })

  it('covers additional correspondent/tag/note fallback branches', () => {
    expect(writebackDisplayValue('correspondent', { id: 7 }, true, 'proposed')).toBe('#7')
    expect(writebackDisplayValue('correspondent', { name: 'OnlyName' }, true, 'proposed')).toBe('OnlyName')
    expect(writebackDisplayValue('tags', { ids: [1, '2'] }, true, 'proposed')).toBe('1, 2')
    expect(writebackDisplayValue('tags', { ids: [] }, true, 'proposed')).toBe('-')
    expect(writebackDisplayValue('note', { id: 1 }, true, 'proposed')).toBe('-')
    expect(writebackDisplayValue('meta', { a: 1 }, true, 'proposed')).toBe('{"a":1}')
  })
})
