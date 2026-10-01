import { computed, ref, watch, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
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
  const searchQuery = ref('')

  // Mirrors queryKey entries after [name, page, pageSize].
  const currentFilterKey = computed(() =>
    [
      ordering.value,
      selectedTag.value,
      selectedCorrespondent.value,
      selectedReviewStatus.value,
      dateFrom.value,
      dateTo.value,
      searchQuery.value.trim(),
      options?.includeSummaryPreview?.value ?? false,
    ].join('|'),
  )

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
      searchQuery.value.trim(),
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
        q: searchQuery.value.trim() || undefined,
        include_derived: true,
        include_summary_preview: options?.includeSummaryPreview?.value ?? false,
        review_status: selectedReviewStatus.value,
      }),
    // Keep the old rows only while paging/ordering within the same filter set;
    // a filter change must never show rows that do not match the new filter.
    placeholderData: (previousData, previousQuery) => {
      const prevKey = previousQuery?.queryKey
      if (!previousData || !prevKey) return undefined
      const sameFilters = prevKey.slice(3).join('|') === currentFilterKey.value
      return sameFilters ? previousData : undefined
    },
    staleTime: 10_000,
  })

  // A server-side search changes the result set, so reset to the first page
  // whenever the query changes (mirrors the existing filter-reset behavior).
  watch(searchQuery, () => {
    page.value = 1
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
    searchQuery,
    documents,
    totalCount,
    tags,
    correspondents,
    documentsLoading: listQuery.isPending,
    documentsError: computed(() => listQuery.isError.value),
    refetchDocuments,
  }
}
