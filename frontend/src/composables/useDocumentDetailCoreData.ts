import { ref } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import {
  type DocumentDetail,
  type DocumentType,
  type PageText,
  type VisionProgress,
  type Tag,
  type Correspondent,
  getCorrespondents,
  getDocumentLocal,
  getDocumentType,
  getPageTexts,
  getTags,
  getTextQuality,
  getOcrScores,
} from '../services/documents'
import type { DocumentOcrScoreOut, TextQualityMetrics } from '@/api/generated/model'

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

export const useDocumentDetailCoreData = () => {
  const document = ref<DocumentDetail | null>(null)
  const loading = ref(false)
  const syncing = ref(false)
  const tags = ref<Tag[]>([])
  const correspondents = ref<Correspondent[]>([])
  const docTypes = ref<DocumentType[]>([])
  const pageTexts = ref<PageText[]>([])
  const pageTextsVisionProgress = ref<VisionProgress | null>(null)
  const pageTextsLoading = ref(false)
  const pageTextsError = ref('')
  const contentQuality = ref<TextQualityMetrics | null>(null)
  const contentQualityLoading = ref(false)
  const contentQualityError = ref('')
  const ocrScores = ref<DocumentOcrScoreOut[]>([])
  const ocrScoresLoading = ref(false)
  const ocrScoresError = ref('')

  const loadDocumentMutation = useMutation({
    mutationFn: (id: number) => getDocumentLocal(id),
  })
  const loadMetaMutation = useMutation({
    mutationFn: async () => {
      const [tagsResp, corrResp] = await Promise.all([getTags(), getCorrespondents()])
      let fetchedDocType: DocumentType | null = null
      if (document.value?.document_type) {
        fetchedDocType = await getDocumentType(document.value.document_type)
      }
      return {
        tags: tagsResp.results ?? [],
        correspondents: corrResp.results ?? [],
        docType: fetchedDocType,
      }
    },
  })
  const loadPageTextsMutation = useMutation({
    mutationFn: ({ id, priority }: { id: number; priority: boolean }) => getPageTexts(id, priority),
  })
  const loadContentQualityMutation = useMutation({
    mutationFn: ({ id, priority }: { id: number; priority: boolean }) => getTextQuality(id, priority),
  })
  const loadOcrScoresMutation = useMutation({
    mutationFn: ({ id, refresh }: { id: number; refresh: boolean }) =>
      getOcrScores(id, refresh ? { refresh } : undefined),
  })

  const resetDerivedState = () => {
    pageTexts.value = []
    pageTextsVisionProgress.value = null
    pageTextsError.value = ''
    contentQuality.value = null
    contentQualityError.value = ''
    ocrScores.value = []
    ocrScoresLoading.value = false
    ocrScoresError.value = ''
  }

  const loadDocument = async (id: number) => {
    loading.value = true
    try {
      const data = await loadDocumentMutation.mutateAsync(id)
      if (data?.status === 'missing') {
        document.value = null
      } else {
        document.value = data
      }
      resetDerivedState()
    } finally {
      loading.value = false
    }
  }

  const loadMeta = async () => {
    const data = await loadMetaMutation.mutateAsync()
    tags.value = data.tags
    correspondents.value = data.correspondents
    docTypes.value = data.docType ? [data.docType] : []
  }

  const loadPageTexts = async (id: number, priority = false) => {
    pageTextsLoading.value = true
    pageTextsError.value = ''
    try {
      const data = await loadPageTextsMutation.mutateAsync({ id, priority })
      pageTexts.value = data.pages ?? []
      pageTextsVisionProgress.value = data.vision_progress ?? null
    } catch (err: unknown) {
      pageTextsError.value = errorMessage(err, 'Failed to load page texts')
      pageTextsVisionProgress.value = null
    } finally {
      pageTextsLoading.value = false
    }
  }

  const loadContentQuality = async (id: number, priority = false) => {
    contentQualityLoading.value = true
    contentQualityError.value = ''
    try {
      const data = await loadContentQualityMutation.mutateAsync({ id, priority })
      contentQuality.value = data.quality ?? null
    } catch (err: unknown) {
      contentQualityError.value = errorMessage(err, 'Failed to load text quality')
    } finally {
      contentQualityLoading.value = false
    }
  }

  const loadOcrScores = async (id: number, refresh = false) => {
    ocrScoresLoading.value = true
    ocrScoresError.value = ''
    try {
      const data = await loadOcrScoresMutation.mutateAsync({ id, refresh })
      ocrScores.value = data.scores ?? []
    } catch (err: unknown) {
      ocrScoresError.value = errorMessage(err, 'Failed to load OCR scores')
    } finally {
      ocrScoresLoading.value = false
    }
  }

  return {
    document,
    loading,
    syncing,
    tags,
    correspondents,
    docTypes,
    pageTexts,
    pageTextsVisionProgress,
    pageTextsLoading,
    pageTextsError,
    contentQuality,
    contentQualityLoading,
    contentQualityError,
    ocrScores,
    ocrScoresLoading,
    ocrScoresError,
    loadDocument,
    loadMeta,
    loadPageTexts,
    loadContentQuality,
    loadOcrScores,
  }
}
