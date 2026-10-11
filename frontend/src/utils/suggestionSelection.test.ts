import { describe, expect, it } from 'vitest'
import { isNewTabClick, isPlainLeftClick, mergeTagNames } from './suggestionSelection'

describe('mergeTagNames', () => {
  it('merges groups case-insensitively without duplicates and keeps order', () => {
    expect(mergeTagNames(['Rechnung', 'Arzt'], ['arzt', ' Hotel '], ['Rechnung'])).toEqual([
      'Rechnung',
      'Arzt',
      'Hotel',
    ])
  })

  it('ignores empty and nullish input', () => {
    expect(mergeTagNames(null, undefined, ['', '  '])).toEqual([])
  })
})

describe('click helpers', () => {
  const click = (init: Partial<MouseEvent>) => init as MouseEvent

  it('detects plain left clicks', () => {
    expect(isPlainLeftClick(click({ button: 0 }))).toBe(true)
    expect(isPlainLeftClick(click({ button: 0, ctrlKey: true }))).toBe(false)
    expect(isPlainLeftClick(click({ button: 1 }))).toBe(false)
  })

  it('detects new-tab clicks', () => {
    expect(isNewTabClick(click({ button: 1 }))).toBe(true)
    expect(isNewTabClick(click({ button: 0, metaKey: true }))).toBe(true)
    expect(isNewTabClick(click({ button: 0 }))).toBe(false)
  })
})
