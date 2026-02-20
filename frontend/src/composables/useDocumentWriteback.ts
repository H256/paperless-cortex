import { computed, ref, type Ref } from 'vue'
import {
  executeWritebackDirectForDocument,
  type WritebackConflictField,
} from '../services/writeback'

type ResolutionValue = 'skip' | 'use_paperless' | 'use_local'

type DocumentWritebackState = {
  local_overrides?: unknown
  review_status?: string | null
  paperless_modified?: string | null
}

type UseDocumentWritebackParams = {
  docId: number
  document: Ref<DocumentWritebackState | null | undefined>
  reloadAll: () => Promise<void>
  toErrorMessage: (err: unknown, fallback: string) => string
  pushToast: (message: string, level: 'success' | 'warning' | 'info' | 'danger', title: string, timeoutMs?: number) => void
}

export const useDocumentWriteback = ({
  docId,
  document,
  reloadAll,
  toErrorMessage,
  pushToast,
}: UseDocumentWritebackParams) => {
  const writebackRunning = ref(false)
  const writebackConfirmOpen = ref(false)
  const writebackConflictOpen = ref(false)
  const writebackConflicts = ref<WritebackConflictField[]>([])
  const writebackResolutions = ref<Record<string, ResolutionValue>>({})
  const writebackErrorOpen = ref(false)
  const writebackErrorMessage = ref('')

  const hasLocalWritebackChanges = computed(() => Boolean(document.value?.local_overrides))
  const canWriteback = computed(() => {
    if (!document.value) return false
    return hasLocalWritebackChanges.value || document.value.review_status === 'needs_review'
  })

  const writebackButtonTitle = computed(() => {
    if (writebackRunning.value) return 'Writeback is currently running'
    if (canWriteback.value) return 'Write local changes back to Paperless'
    return 'No local changes detected for writeback'
  })

  const writebackButtonLabel = computed(() => {
    if (writebackRunning.value) return 'Writing back...'
    if (canWriteback.value) return 'Write back'
    return 'No changes to write back'
  })

  const setConflictResolution = (field: string, value: ResolutionValue) => {
    writebackResolutions.value = { ...writebackResolutions.value, [field]: value }
  }

  const closeWritebackError = () => {
    writebackErrorOpen.value = false
  }

  const resetConflictState = () => {
    writebackConflicts.value = []
    writebackResolutions.value = {}
  }

  const runWritebackNowForDocument = async (
    resolutions?: Record<string, ResolutionValue>,
  ) => {
    writebackRunning.value = true
    writebackErrorMessage.value = ''
    try {
      const result = await executeWritebackDirectForDocument(docId, {
        known_paperless_modified: document.value?.paperless_modified ?? null,
        resolutions: resolutions ?? {},
      })
      if (result.status === 'conflicts') {
        writebackConflicts.value = result.conflicts || []
        writebackResolutions.value = Object.fromEntries(
          writebackConflicts.value.map((conflict) => [conflict.field, 'skip']),
        ) as Record<string, ResolutionValue>
        writebackConflictOpen.value = true
        pushToast(
          'Conflicts detected. Choose per field how to proceed.',
          'warning',
          'Writeback',
          3000,
        )
        return
      }
      const calls = result.calls_count ?? 0
      const changed = result.docs_changed ?? 0
      if (calls > 0 && changed > 0) {
        pushToast(
          `Writeback executed ${calls} call(s) for ${changed} changed document(s).`,
          'success',
          'Writeback',
          2200,
        )
      } else {
        pushToast(
          'No writeback changes found for this document.',
          'info',
          'Writeback',
          2200,
        )
      }
      await reloadAll()
    } catch (err: unknown) {
      const message = toErrorMessage(err, 'Failed to write back document')
      pushToast(message, 'danger', 'Writeback', 2800)
      writebackErrorMessage.value = message
      writebackErrorOpen.value = true
    } finally {
      writebackRunning.value = false
    }
  }

  const openWritebackConfirm = () => {
    if (!canWriteback.value || writebackRunning.value) return
    writebackConfirmOpen.value = true
  }

  const closeWritebackConfirm = () => {
    writebackConfirmOpen.value = false
  }

  const confirmWritebackNow = async () => {
    writebackConfirmOpen.value = false
    await runWritebackNowForDocument()
  }

  const cancelWritebackConflict = () => {
    writebackConflictOpen.value = false
    resetConflictState()
  }

  const applyWritebackConflictResolutions = async () => {
    writebackConflictOpen.value = false
    await runWritebackNowForDocument({ ...writebackResolutions.value })
    resetConflictState()
  }

  return {
    writebackRunning,
    writebackConfirmOpen,
    writebackConflictOpen,
    writebackConflicts,
    writebackResolutions,
    writebackErrorOpen,
    writebackErrorMessage,
    canWriteback,
    writebackButtonTitle,
    writebackButtonLabel,
    openWritebackConfirm,
    closeWritebackConfirm,
    confirmWritebackNow,
    cancelWritebackConflict,
    applyWritebackConflictResolutions,
    setConflictResolution,
    closeWritebackError,
  }
}
