import { describe, expect, it } from 'vitest'
import { computeAgreement, normalizeAgreementValue } from './suggestionAgreement'

describe('normalizeAgreementValue', () => {
  it('compares titles and names case/punctuation/space insensitively', () => {
    expect(normalizeAgreementValue('correspondent', "Hol'Ab!  Getränkemarkt GmbH")).toBe(
      'holab getränkemarkt gmbh',
    )
    expect(normalizeAgreementValue('title', ' Rechnung  März ')).toBe('rechnung märz')
  })

  it('normalizes dates to the ISO day', () => {
    expect(normalizeAgreementValue('date', '2026-10-10T08:00:00+00:00')).toBe('2026-10-10')
    expect(normalizeAgreementValue('date', '10.10.2026')).toBe('2026-10-10')
    expect(normalizeAgreementValue('date', '1.2.2026')).toBe('2026-02-01')
  })

  it('treats empty and non-string values as no value', () => {
    expect(normalizeAgreementValue('title', '')).toBe('')
    expect(normalizeAgreementValue('title', null)).toBe('')
    expect(normalizeAgreementValue('date', ['2026-10-10'])).toBe('')
  })
})

describe('computeAgreement', () => {
  it('counts sources that carry the same value', () => {
    const result = computeAgreement('date', {
      values: { vision_ocr: '2026-10-10', paperless_ocr: '10.10.2026', similar_docs: '2025-01-01' },
    })
    expect(result.total).toBe(3)
    expect(result.agreeing.vision_ocr).toBe(2)
    expect(result.agreeing.paperless_ocr).toBe(2)
    expect(result.agreeing.similar_docs).toBe(1)
  })

  it('counts the text candidates as an additional source', () => {
    const result = computeAgreement('date', {
      values: { vision_ocr: '2026-10-10', paperless_ocr: '2026-10-11' },
      textValues: ['2026-10-10'],
    })
    expect(result.total).toBe(3)
    expect(result.agreeing.vision_ocr).toBe(2)
    expect(result.textMatches.vision_ocr).toBe(true)
    expect(result.agreeing.paperless_ocr).toBe(1)
    expect(result.textMatches.paperless_ocr).toBe(false)
  })

  it('ignores sources without a value', () => {
    const result = computeAgreement('title', { values: { vision_ocr: 'A', paperless_ocr: '' } })
    expect(result.total).toBe(1)
    expect(result.agreeing).toEqual({ vision_ocr: 1 })
  })
})
