import { computed, ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import {
  cancelEmbeddings,
  cancelSync,
  processMissing,
  type ProcessMissingParams,
} from '../services/documents'
import type { ProcessMissingResponse } from '@/api/generated/model'

export const useContinueProcessing = () => {
  const processPreview = ref<ProcessMissingResponse | null>(null)
  const processStartResult = ref<{ enqueued?: number; tasks?: number } | null>(null)

  const previewMutation = useMutation({
    mutationFn: (options: ProcessMissingParams = {}) => processMissing({ dry_run: true, ...options }),
    onSuccess: (preview) => {
      processPreview.value = preview
      processStartResult.value = null
    },
  })

  const refreshPreviewMutation = useMutation({
    mutationFn: (options: ProcessMissingParams = {}) => processMissing({ dry_run: true, ...options }),
    onSuccess: (preview) => {
      processPreview.value = preview
    },
  })

  const startMutation = useMutation({
    mutationFn: (options: ProcessMissingParams = {}) => processMissing(options),
    onSuccess: (result) => {
      processStartResult.value = { enqueued: result.enqueued, tasks: result.tasks }
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async () => {
      await cancelSync()
      await cancelEmbeddings()
    },
  })

  const processPreviewLoading = computed(
    () => previewMutation.isPending.value || refreshPreviewMutation.isPending.value,
  )
  const processStartLoading = computed(() => startMutation.isPending.value)
  const showPreviewModal = computed(() => processPreview.value !== null)
  const continueProcessingRunning = computed(() => previewMutation.isPending.value)

  const openPreview = async (options: ProcessMissingParams) => previewMutation.mutateAsync(options)
  const refreshProcessPreview = async (options: ProcessMissingParams) =>
    refreshPreviewMutation.mutateAsync(options)
  const startFromPreview = async (options: ProcessMissingParams) => startMutation.mutateAsync(options)
  const cancelProcessing = async () => cancelMutation.mutateAsync()
  const closePreview = () => {
    processPreview.value = null
    processStartResult.value = null
  }

  return {
    processPreview,
    processPreviewLoading,
    processStartResult,
    processStartLoading,
    showPreviewModal,
    continueProcessingRunning,
    openPreview,
    refreshProcessPreview,
    startFromPreview,
    cancelProcessing,
    closePreview,
  }
}
