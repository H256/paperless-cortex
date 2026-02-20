import { describe, expect, it, vi } from 'vitest'
import { useDocumentDetailOperations } from './useDocumentDetailOperations'

const createOps = () => {
  const enqueueDocumentTaskNow = vi.fn(async () => ({ enqueued: 1 }))
  const cleanupDocumentTexts = vi.fn(async () => ({ queued: true, docs: 1 }))
  const continuePipelineRequest = vi.fn(async () => ({ enabled: true, enqueued: 2, missing_tasks: 3 }))
  const resetAndReprocessNow = vi.fn(async () => ({ enqueued: 4 }))
  const load = vi.fn(async () => undefined)
  const refreshTaskRuns = vi.fn(async () => undefined)
  const loadPipelineStatus = vi.fn(async () => undefined)
  const refreshPipelineFanout = vi.fn(async () => undefined)
  const toErrorMessage = vi.fn((err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback,
  )
  const ops = useDocumentDetailOperations({
    docId: 10,
    enqueueDocumentTaskNow,
    cleanupDocumentTexts,
    continuePipelineRequest,
    resetAndReprocessNow,
    load,
    refreshTaskRuns,
    loadPipelineStatus,
    refreshPipelineFanout,
    toErrorMessage,
  })
  return {
    ops,
    enqueueDocumentTaskNow,
    cleanupDocumentTexts,
    continuePipelineRequest,
    resetAndReprocessNow,
    load,
    refreshTaskRuns,
    loadPipelineStatus,
    refreshPipelineFanout,
    toErrorMessage,
  }
}

describe('useDocumentDetailOperations', () => {
  it('queues a task and sets success message', async () => {
    const { ops, loadPipelineStatus, refreshPipelineFanout } = createOps()
    await ops.enqueueDocTask({
      task: 'vision_ocr',
      label: 'Queue vision OCR',
      tooltip: 'x',
      force: true,
    })
    expect(ops.docOpsMessage.value).toContain('Queued task vision_ocr')
    expect(loadPipelineStatus).toHaveBeenCalled()
    expect(refreshPipelineFanout).toHaveBeenCalled()
  })

  it('handles continue pipeline when queue is disabled', async () => {
    const { ops, continuePipelineRequest } = createOps()
    continuePipelineRequest.mockResolvedValueOnce({ enabled: false, enqueued: 0, missing_tasks: 0 })
    await ops.runContinuePipeline()
    expect(ops.docOpsMessage.value).toBe('Queue is disabled.')
    expect(ops.continueQueuedWaiting.value).toBe(false)
  })

  it('sets waiting state and refreshes timeline when continue enqueues work', async () => {
    const { ops, refreshTaskRuns } = createOps()
    await ops.runContinuePipeline()
    expect(ops.docOpsMessage.value).toContain('Enqueued 2/3 missing tasks.')
    expect(ops.continueQueuedWaiting.value).toBe(true)
    expect(refreshTaskRuns).toHaveBeenCalled()
  })

  it('maps retry errors into message via toErrorMessage', async () => {
    const { ops, enqueueDocumentTaskNow, toErrorMessage } = createOps()
    enqueueDocumentTaskNow.mockRejectedValueOnce(new Error('boom'))
    await ops.retryTaskRun({
      task: 'vision_ocr',
      source: 'vision_ocr',
      status: 'failed',
    })
    expect(toErrorMessage).toHaveBeenCalled()
    expect(ops.docOpsMessage.value).toBe('boom')
  })
})
