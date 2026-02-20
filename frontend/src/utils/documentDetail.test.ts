/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest'
import { compactErrorMessage, formatDocDate, parseBBox, queryToRecord, toTitle } from './documentDetail'

describe('documentDetail utils', () => {
  it('parses bbox from query', () => {
    expect(parseBBox('1,2,3,4')).toEqual([1, 2, 3, 4])
    expect(parseBBox('x,2,3,4')).toBeNull()
  })

  it('formats title and dates', () => {
    expect(toTitle('needs_review')).toBe('Needs Review')
    expect(formatDocDate('2026-02-20')).not.toBe('')
  })

  it('normalizes query maps and errors', () => {
    expect(queryToRecord({ tab: 'meta', page: ['2'] } as never, ['tab'])).toEqual({ page: '2' })
    expect(compactErrorMessage('a'.repeat(140))).toContain('...')
  })
})
