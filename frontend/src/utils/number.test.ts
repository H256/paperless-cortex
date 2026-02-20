import { describe, expect, it } from 'vitest'
import { toOptionalNumber } from './number'

describe('number utils', () => {
  it('returns parsed numbers', () => {
    expect(toOptionalNumber('5')).toBe(5)
    expect(toOptionalNumber('5.5')).toBe(5.5)
  })

  it('returns undefined for empty or invalid input', () => {
    expect(toOptionalNumber('')).toBeUndefined()
    expect(toOptionalNumber('abc')).toBeUndefined()
  })
})
