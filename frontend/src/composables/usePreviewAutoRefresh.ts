import { watch, type Ref } from 'vue'

type RefreshFn = (options: Record<string, unknown>) => Promise<unknown>

export const usePreviewAutoRefresh = (
  processOptions: Record<string, unknown>,
  batchIndex: Ref<number>,
  showPreviewModal: Ref<boolean>,
  processParams: () => Record<string, unknown>,
  refreshProcessPreview: RefreshFn,
) => {
  watch(
    () => ({ ...processOptions }),
    async () => {
      if (!showPreviewModal.value) return
      try {
        await refreshProcessPreview(processParams())
      } catch {
        // Keep current preview shown when transient refresh fails.
      }
    },
    { deep: true },
  )

  watch(batchIndex, async () => {
    if (!showPreviewModal.value) return
    try {
      await refreshProcessPreview(processParams())
    } catch {
      // Keep current preview shown when transient refresh fails.
    }
  })
}
