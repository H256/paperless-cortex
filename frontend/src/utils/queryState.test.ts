import { describe, expect, it } from 'vitest'
import { isSameQueryState, queryBool, queryNumber, queryString } from './queryState'

describe('queryState utils', () => {
  it('parses strings and falls back', () => {
    expect(queryString('abc', 'x')).toBe('abc')
    expect(queryString(['def'], 'x')).toBe('def')
    expect(queryString(123, 'x')).toBe('x')
  })

  it('parses booleans and falls back', () => {
    expect(queryBool('1', false)).toBe(true)
    expect(queryBool('true', false)).toBe(true)
    expect(queryBool('0', true)).toBe(false)
    expect(queryBool('false', true)).toBe(false)
    expect(queryBool('other', true)).toBe(true)
  })

  it('parses numbers and falls back', () => {
    expect(queryNumber('42', 1)).toBe(42)
    expect(queryNumber(['7'], 1)).toBe(7)
    expect(queryNumber('x', 1)).toBe(1)
  })

  it('compares query state maps', () => {
    expect(isSameQueryState({ page: '2', sort: 'date' }, { page: '2', sort: 'date' })).toBe(true)
    expect(isSameQueryState({ page: ['2'] }, { page: '2' })).toBe(true)
    expect(isSameQueryState({ page: '2' }, { page: '3' })).toBe(false)
  })
})
