import type { Ref } from 'vue'
import { ref } from 'vue'
import type { ToastTone } from '../stores/toastStore'

type ToastLike = {
  push: (message: string, tone?: ToastTone, title?: string, durationMs?: number) => void
}

type ContinueProcessingApi = {
  processStartResult: Ref<{ enqueued?: number; tasks?: number } | null>
  openPreviewRequest: (options: Record<string, unknown>) => Promise<unknown>
  startFromPreviewRequest: (options: Record<string, unknown>) => Promise<unknown>
  cancelProcessingRequest: () => Promise<unknown>
  clearPreviewState: () => void
}

type ProcessingOverviewApi = {
  refreshProcessingOverview: () => Promise<unknown>
  clearQueueNow: () => Promise<unknown>
}

export const useDocumentsProcessingActions = (
  toastStore: ToastLike,
  continueApi: ContinueProcessingApi,
  overviewApi: ProcessingOverviewApi,
  loadDocuments: () => Promise<void>,
  processParams: () => Record<string, unknown>,
) => {
  const processingKickoffPending = ref(false)

  const refreshAfterProcessingMutation = async () => {
    await Promise.all([overviewApi.refreshProcessingOverview(), loadDocuments()])
  }

  const openPreview = async () => {
    try {
      await continueApi.openPreviewRequest(processParams())
      await refreshAfterProcessingMutation()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to prepare processing preview'
      toastStore.push(message, 'danger', 'Processing')
    }
  }

  const closePreview = () => {
    continueApi.clearPreviewState()
  }

  const startFromPreview = async () => {
    processingKickoffPending.value = true
    try {
      await continueApi.startFromPreviewRequest(processParams())
      if (continueApi.processStartResult.value) {
        toastStore.push(
          `Enqueued ${continueApi.processStartResult.value.enqueued ?? 0} docs (${continueApi.processStartResult.value.tasks ?? 0} tasks).`,
          'success',
          'Queue started',
        )
      }
      continueApi.clearPreviewState()
      await refreshAfterProcessingMutation()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start processing'
      toastStore.push(message, 'danger', 'Processing')
    } finally {
      processingKickoffPending.value = false
    }
  }

  const cancelProcessing = async () => {
    try {
      await continueApi.cancelProcessingRequest()
      await overviewApi.clearQueueNow()
      await refreshAfterProcessingMutation()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to cancel processing'
      toastStore.push(message, 'danger', 'Processing')
    }
  }

  return {
    processingKickoffPending,
    refreshAfterProcessingMutation,
    openPreview,
    closePreview,
    startFromPreview,
    cancelProcessing,
  }
}
