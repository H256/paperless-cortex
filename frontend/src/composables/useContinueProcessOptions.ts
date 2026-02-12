import { computed, reactive, ref } from 'vue'

export const useContinueProcessOptions = () => {
  const processOptions = reactive({
    includeSync: true,
    strategy: 'balanced' as 'balanced' | 'paperless_only' | 'vision_first' | 'max_coverage',
  })

  const batchOptions = [10, 20, 50, 100, 200, 500, 'All'] as const
  const batchIndex = ref(batchOptions.length - 1)
  const batchLimit = computed(() => {
    const value = batchOptions[batchIndex.value]
    return value === 'All' ? null : value
  })
  const batchLabel = computed(() => (batchLimit.value === null ? 'All' : String(batchLimit.value)))

  const derived = computed(() => {
    if (processOptions.strategy === 'paperless_only') {
      return {
        include_vision_ocr: false,
        include_embeddings: true,
        include_embeddings_paperless: true,
        include_embeddings_vision: false,
        embeddings_mode: 'paperless' as const,
        include_page_notes: false,
        include_summary_hierarchical: false,
        include_suggestions_paperless: true,
        include_suggestions_vision: false,
      }
    }
    if (processOptions.strategy === 'vision_first') {
      return {
        include_vision_ocr: true,
        include_embeddings: true,
        include_embeddings_paperless: false,
        include_embeddings_vision: true,
        embeddings_mode: 'vision' as const,
        include_page_notes: true,
        include_summary_hierarchical: true,
        include_suggestions_paperless: false,
        include_suggestions_vision: true,
      }
    }
    if (processOptions.strategy === 'max_coverage') {
      return {
        include_vision_ocr: true,
        include_embeddings: true,
        include_embeddings_paperless: true,
        include_embeddings_vision: true,
        embeddings_mode: 'both' as const,
        include_page_notes: true,
        include_summary_hierarchical: true,
        include_suggestions_paperless: true,
        include_suggestions_vision: true,
      }
    }
    return {
      include_vision_ocr: true,
      include_embeddings: true,
      include_embeddings_paperless: true,
      include_embeddings_vision: true,
      embeddings_mode: 'auto' as const,
      include_page_notes: true,
      include_summary_hierarchical: true,
      include_suggestions_paperless: true,
      include_suggestions_vision: true,
    }
  })

  const processParams = () => ({
    include_sync: processOptions.includeSync,
    include_vision_ocr: derived.value.include_vision_ocr,
    include_embeddings: derived.value.include_embeddings,
    include_embeddings_paperless: derived.value.include_embeddings_paperless,
    include_embeddings_vision: derived.value.include_embeddings_vision,
    embeddings_mode: derived.value.embeddings_mode,
    include_page_notes: derived.value.include_page_notes,
    include_summary_hierarchical: derived.value.include_summary_hierarchical,
    include_suggestions_paperless: derived.value.include_suggestions_paperless,
    include_suggestions_vision: derived.value.include_suggestions_vision,
    limit: batchLimit.value ?? undefined,
  })

  return {
    processOptions,
    strategySummary: derived,
    batchOptions,
    batchIndex,
    batchLimit,
    batchLabel,
    processParams,
  }
}
