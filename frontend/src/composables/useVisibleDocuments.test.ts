import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import { useVisibleDocuments } from './useVisibleDocuments'

describe('useVisibleDocuments', () => {
  const docs = ref([
    {
      id: 1,
      title: 'Invoice A',
      correspondent_name: 'Alpha',
      content: 'utility bill',
      has_embeddings: true,
      has_suggestions: false,
      has_vision_pages: false,
      analysis_model: 'gpt-4o',
    },
    {
      id: 2,
      title: 'Letter B',
      correspondent_name: 'Beta',
      content: 'plain letter',
      has_embeddings: false,
      has_suggestions: false,
      has_vision_pages: false,
      analysis_model: '',
    },
  ] as never[])

  it('filters analyzed docs', () => {
    const analysisFilter = ref<'all' | 'analyzed' | 'not_analyzed'>('analyzed')
    const modelFilter = ref('')
    const searchQuery = ref('')
    const { visibleDocuments } = useVisibleDocuments(docs, analysisFilter, modelFilter, searchQuery)
    expect(visibleDocuments.value).toHaveLength(1)
    expect(visibleDocuments.value[0]?.id).toBe(1)
  })

  it('filters by model and search query', () => {
    const analysisFilter = ref<'all' | 'analyzed' | 'not_analyzed'>('all')
    const modelFilter = ref('gpt')
    const searchQuery = ref('invoice')
    const { visibleDocuments } = useVisibleDocuments(docs, analysisFilter, modelFilter, searchQuery)
    expect(visibleDocuments.value).toHaveLength(1)
    expect(visibleDocuments.value[0]?.title).toBe('Invoice A')
  })
})
