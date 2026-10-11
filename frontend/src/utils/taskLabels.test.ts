import { describe, expect, it } from 'vitest'
import { describeRunningTask, processingPillLabel, taskLabel } from './taskLabels'

describe('taskLabel', () => {
  it('maps known tasks and makes unknown ones readable', () => {
    expect(taskLabel('vision_ocr')).toBe('Vision OCR')
    expect(taskLabel('suggest_field')).toBe('New suggestion')
    expect(taskLabel('some_new_task')).toBe('some new task')
    expect(taskLabel('')).toBe('Task')
    expect(taskLabel(null)).toBe('Task')
  })
})

describe('processingPillLabel', () => {
  it('names what is running and counts parallel tasks', () => {
    const tasks = [
      { docId: 2210, label: 'Vision OCR 3/12' },
      { docId: 2211, label: 'Embeddings' },
    ]
    expect(describeRunningTask(tasks[0]!)).toBe('Vision OCR 3/12 · #2210')
    expect(processingPillLabel('Processing 4/10', tasks)).toBe(
      'Processing 4/10 · Vision OCR 3/12 · #2210 +1',
    )
  })

  it('falls back to the counts when nothing is known to run', () => {
    expect(processingPillLabel('Queue 3', [])).toBe('Queue 3')
    expect(describeRunningTask({ docId: null, label: 'Sync' })).toBe('Sync')
  })
})
