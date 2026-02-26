import { ref } from 'vue'
import type { DocumentOperationTaskPayload } from '../services/documents'

export type OperationAction = {
  task: Extract<
    DocumentOperationTaskPayload['task'],
    | 'vision_ocr'
    | 'embeddings_vision'
    | 'similarity_index'
    | 'page_notes_vision'
    | 'summary_hierarchical'
    | 'suggestions_paperless'
    | 'suggestions_vision'
  >
  label: string
  tooltip: string
  force?: boolean
  source?: 'paperless_ocr' | 'vision_ocr'
}

export type TimelineTaskRun = {
  task: string
  source?: string | null
  status: string
}

type UseDocumentDetailOperationsArgs = {
  docId: number
  enqueueDocumentTaskNow: (payload: DocumentOperationTaskPayload) => Promise<{ enqueued?: boolean | number }>
  cleanupDocumentTexts: (clearFirst: boolean) => Promise<{ queued: boolean; docs?: number; updated?: number; processed?: number }>
  continuePipelineRequest: (payload: {
    include_vision_ocr: boolean
    include_embeddings: boolean
    include_embeddings_paperless: boolean
    include_embeddings_vision: boolean
    include_page_notes: boolean
    include_summary_hierarchical: boolean
    include_suggestions_paperless: boolean
    include_suggestions_vision: boolean
  }) => Promise<{ enabled: boolean; enqueued?: number; missing_tasks?: number }>
  resetAndReprocessNow: (force: boolean) => Promise<{ enqueued: number }>
  load: () => Promise<void>
  refreshTaskRuns: () => Promise<unknown>
  loadPipelineStatus: () => Promise<unknown>
  refreshPipelineFanout: () => Promise<unknown>
  toErrorMessage: (err: unknown, fallback: string) => string
}

export const operationActions: OperationAction[] = [
  {
    task: 'vision_ocr',
    label: 'Queue vision OCR',
    tooltip: 'Triggers vision OCR again for pages of this document.',
    force: true,
  },
  {
    task: 'embeddings_vision',
    label: 'Queue embeddings (vision)',
    tooltip: 'Erstellt Embeddings aus Vision-OCR-Text und speichert sie in Qdrant.',
  },
  {
    task: 'similarity_index',
    label: 'Queue similarity index',
    tooltip: 'Erstellt/aktualisiert den Doc-Level Similarity-Vektor aus vorhandenen Chunk-Embeddings.',
  },
  {
    task: 'page_notes_vision',
    label: 'Queue page notes (vision)',
    tooltip: 'Generates structured page notes from vision OCR per page.',
  },
  {
    task: 'summary_hierarchical',
    label: 'Queue hierarchical summary',
    tooltip: 'Aggregates page notes by section and builds a hierarchical summary.',
    source: 'vision_ocr',
  },
  {
    task: 'suggestions_paperless',
    label: 'Queue suggestions (paperless)',
    tooltip: 'Generates suggestion fields from Paperless OCR text.',
  },
  {
    task: 'suggestions_vision',
    label: 'Queue suggestions (vision)',
    tooltip: 'Generates suggestion fields from vision OCR text.',
  },
]

export const useDocumentDetailOperations = (args: UseDocumentDetailOperationsArgs) => {
  const docOpsMessage = ref('')
  const docCleanupClearFirst = ref(false)
  const resetConfirmOpen = ref(false)
  const continueQueuedWaiting = ref(false)
  const continueQueuedExpireAt = ref(0)

  const withDocOperation = async (fn: () => Promise<void>) => {
    docOpsMessage.value = ''
    await fn()
    await args.loadPipelineStatus()
    await args.refreshPipelineFanout()
  }

  const enqueueDocTask = async (action: OperationAction) => {
    await withDocOperation(async () => {
      try {
        const result = await args.enqueueDocumentTaskNow({
          task: action.task,
          force: action.force ?? false,
          source: action.source,
        })
        docOpsMessage.value = Number(result.enqueued || 0) > 0
          ? `Queued task ${action.task} for document ${args.docId}.`
          : `Task ${action.task} was not enqueued (possibly duplicate/running).`
      } catch (err) {
        docOpsMessage.value = args.toErrorMessage(err, `Failed to queue ${action.task}`)
      }
    })
  }

  const retryTaskRun = async (run: TimelineTaskRun) => {
    const task = String(run.task || '').trim() as DocumentOperationTaskPayload['task']
    if (!task) return
    await withDocOperation(async () => {
      try {
        const result = await args.enqueueDocumentTaskNow({
          task,
          source: run.source === 'paperless_ocr' || run.source === 'vision_ocr' ? run.source : undefined,
        })
        docOpsMessage.value = Number(result.enqueued || 0) > 0
          ? `Queued retry for ${task}.`
          : `Retry for ${task} was not enqueued (duplicate or already running).`
        await args.refreshTaskRuns()
      } catch (err) {
        docOpsMessage.value = args.toErrorMessage(err, `Failed to retry ${task}`)
      }
    })
  }

  const runDocCleanup = async () => {
    await withDocOperation(async () => {
      try {
        const result = await args.cleanupDocumentTexts(docCleanupClearFirst.value)
        docOpsMessage.value = result.queued
          ? `Queued cleanup for ${result.docs} document(s).`
          : `Cleanup done: ${result.updated}/${result.processed} updated.`
      } catch (err) {
        docOpsMessage.value = args.toErrorMessage(err, 'Failed to queue cleanup')
      }
    })
  }

  const runContinuePipeline = async () => {
    await withDocOperation(async () => {
      try {
        continueQueuedWaiting.value = false
        continueQueuedExpireAt.value = 0
        const result = await args.continuePipelineRequest({
          include_vision_ocr: true,
          include_embeddings: true,
          include_embeddings_paperless: true,
          include_embeddings_vision: true,
          include_page_notes: true,
          include_summary_hierarchical: true,
          include_suggestions_paperless: true,
          include_suggestions_vision: true,
        })
        if (!result.enabled) {
          docOpsMessage.value = 'Queue is disabled.'
          return
        }
        docOpsMessage.value = result.enqueued
          ? `Enqueued ${result.enqueued}/${result.missing_tasks ?? 0} missing tasks.`
          : 'No missing tasks.'
        if ((result.enqueued || 0) > 0) {
          continueQueuedWaiting.value = true
          continueQueuedExpireAt.value = Date.now() + 120_000
          await Promise.all([args.refreshTaskRuns(), args.loadPipelineStatus(), args.refreshPipelineFanout()])
        }
      } catch (err) {
        docOpsMessage.value = args.toErrorMessage(err, 'Failed to continue document pipeline')
        continueQueuedWaiting.value = false
        continueQueuedExpireAt.value = 0
      }
    })
  }

  const runResetAndReprocessDoc = async () => {
    await withDocOperation(async () => {
      try {
        const result = await args.resetAndReprocessNow(true)
        docOpsMessage.value = `Document reset/synced. Enqueued ${result.enqueued} tasks.`
        await args.load()
      } catch (err) {
        docOpsMessage.value = args.toErrorMessage(err, 'Failed to reset and reprocess document')
      }
    })
  }

  const openResetConfirm = () => {
    resetConfirmOpen.value = true
  }

  const confirmResetAndReprocessDoc = async () => {
    resetConfirmOpen.value = false
    await runResetAndReprocessDoc()
  }

  return {
    docOpsMessage,
    docCleanupClearFirst,
    resetConfirmOpen,
    continueQueuedWaiting,
    continueQueuedExpireAt,
    operationActions,
    enqueueDocTask,
    retryTaskRun,
    runDocCleanup,
    runContinuePipeline,
    openResetConfirm,
    confirmResetAndReprocessDoc,
  }
}
