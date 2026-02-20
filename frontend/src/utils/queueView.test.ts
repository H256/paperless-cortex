import { describe, expect, it } from 'vitest'
import {
  delayedDocId,
  delayedTaskLabel,
  queueCompactMessage,
  queueFormatDueIn,
  queueItemDescription,
  queueItemTitle,
} from './queueView'

describe('queueView utils', () => {
  it('formats queue item labels', () => {
    expect(queueItemTitle({ doc_id: 5, task: 'sync' })).toContain('Doc 5')
    expect(queueItemDescription({ doc_id: 5, task: 'sync' })).toContain('Fetch latest')
  })

  it('formats due values and compact message', () => {
    expect(queueFormatDueIn(65)).toBe('1m 5s')
    expect(queueCompactMessage('a'.repeat(150))).toContain('...')
  })

  it('extracts delayed task metadata', () => {
    expect(delayedTaskLabel({ task: { task: 'vision_ocr' } })).toBe('vision_ocr')
    expect(delayedDocId({ task: { doc_id: 88 } })).toBe('88')
  })
})
