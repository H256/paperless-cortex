import { computed, ref, type Ref } from 'vue'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { getCorrespondents, getTags, listDocuments, type DocumentRow } from '../services/documents'
import { toOptionalNumber } from '../utils/number'

export const useDocumentsCatalog = (options?: { includeSummaryPreview?: Ref<boolean> }) => {
  const page = ref(1)
  const pageSize = ref(20)
  const ordering = ref('-date')
  const selectedTag = ref('')
  const selectedCorrespondent = ref('')
  const selectedReviewStatus = ref<'all' | 'unreviewed' | 'reviewed' | 'needs_review'>('all')
  const dateFrom = ref('')
  const dateTo = ref('')

  const listQuery = useQuery({
    queryKey: computed(() => [
      'documents-list',
      page.value,
      pageSize.value,
      ordering.value,
      selectedTag.value,
      selectedCorrespondent.value,
      selectedReviewStatus.value,
      dateFrom.value,
      dateTo.value,
      options?.includeSummaryPreview?.value ?? false,
    ]),
    queryFn: () =>
      listDocuments({
        page: page.value,
        page_size: pageSize.value,
        ordering: ordering.value,
        correspondent__id: toOptionalNumber(selectedCorrespondent.value),
        tags__id: toOptionalNumber(selectedTag.value),
        document_date__gte: dateFrom.value || undefined,
        document_date__lte: dateTo.value || undefined,
        include_derived: true,
        include_summary_preview: options?.includeSummaryPreview?.value ?? false,
        review_status: selectedReviewStatus.value,
      }),
    placeholderData: keepPreviousData,
    staleTime: 10_000,
  })

  const metaQuery = useQuery({
    queryKey: ['documents-meta'],
    queryFn: async () => {
      const [tagsResp, corrResp] = await Promise.allSettled([getTags(), getCorrespondents()])
      return {
        tags: tagsResp.status === 'fulfilled' ? (tagsResp.value.results ?? []) : [],
        correspondents: corrResp.status === 'fulfilled' ? (corrResp.value.results ?? []) : [],
      }
    },
    staleTime: 120_000,
  })

  const documents = computed<DocumentRow[]>(() => listQuery.data.value?.results ?? [])
  const totalCount = computed(() => listQuery.data.value?.count ?? documents.value.length)
  const tags = computed(() => metaQuery.data.value?.tags ?? [])
  const correspondents = computed(() => metaQuery.data.value?.correspondents ?? [])

  const refetchDocuments = async () => listQuery.refetch()

  return {
    page,
    pageSize,
    ordering,
    selectedTag,
    selectedCorrespondent,
    selectedReviewStatus,
    dateFrom,
    dateTo,
    documents,
    totalCount,
    tags,
    correspondents,
    documentsLoading: listQuery.isPending,
    refetchDocuments,
  }
}
