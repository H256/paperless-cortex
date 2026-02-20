import { describe, expect, it } from 'vitest'
import type { ChatCitation } from '../api/generated/model'
import {
  citationClass,
  evidenceConfidence,
  evidenceError,
  evidenceStatus,
  formatRelativeAge,
  shortConversationId,
} from './chatPresentation'

describe('chatPresentation', () => {
  it('formats relative age buckets', () => {
    const now = 1_000_000
    expect(formatRelativeAge(now, now - 2_000)).toBe('just now')
    expect(formatRelativeAge(now, now - 12_000)).toBe('12s ago')
    expect(formatRelativeAge(now, now - 3_600_000)).toBe('1h ago')
  })

  it('formats evidence metadata safely', () => {
    const citation = {
      evidence_status: 'ok',
      evidence_confidence: 0.923,
      evidence_error: 'none',
    } as ChatCitation
    expect(evidenceStatus(citation)).toBe('ok')
    expect(evidenceConfidence(citation)).toBe('0.92')
    expect(evidenceError(citation)).toBe('none')
    expect(citationClass(citation)).toContain('emerald')
  })

  it('shortens long conversation ids', () => {
    expect(shortConversationId('abc')).toBe('abc')
    expect(shortConversationId('1234567890abcdef')).toBe('12345678...cdef')
  })
})
