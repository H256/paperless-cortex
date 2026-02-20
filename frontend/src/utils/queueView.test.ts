import { describe, expect, it, vi } from 'vitest'
import {
  delayedDocId,
  delayedTaskLabel,
  queueCompactMessage,
  queueFormatRuntime,
  queueFormatStartedAt,
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

  it('covers unknown and fallback queue branches', () => {
    expect(queueItemTitle({ doc_id: 9, task: 'custom_task' })).toBe('Doc 9 - custom_task')
    expect(queueItemTitle({ raw: 'manual payload' })).toBe('manual payload')
    expect(queueItemDescription({ doc_id: 9, task: 'custom_task' })).toBe('Unknown queue item')
    expect(queueItemDescription({ raw: 'manual payload' })).toBe('Custom queue payload')
    expect(delayedTaskLabel({ task: null })).toBe('unknown')
    expect(delayedDocId({ task: null })).toBe('-')
  })

  it('formats runtime and started-at values', () => {
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(3_600_000)
    expect(queueFormatRuntime(3590)).toBe('10s')
    expect(queueFormatRuntime(3000)).toBe('10m 0s')
    expect(queueFormatRuntime(0)).toBe('1h 0m')
    nowSpy.mockRestore()
    expect(typeof queueFormatStartedAt(1_700_000_000)).toBe('string')
  })
})
