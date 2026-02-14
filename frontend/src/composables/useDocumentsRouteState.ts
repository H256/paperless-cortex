import { onMounted, ref, watch, type Ref } from 'vue'
import type { LocationQuery } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'

type AnalysisFilter = 'all' | 'analyzed' | 'not_analyzed'
type ReviewStatus = 'all' | 'unreviewed' | 'reviewed' | 'needs_review'
type ViewMode = 'table' | 'cards'

type RouteStateRefs = {
  page: Ref<number>
  pageSize: Ref<number>
  ordering: Ref<string>
  selectedTag: Ref<string>
  selectedCorrespondent: Ref<string>
  selectedReviewStatus: Ref<ReviewStatus>
  dateFrom: Ref<string>
  dateTo: Ref<string>
  analysisFilter: Ref<AnalysisFilter>
  modelFilter: Ref<string>
  searchQuery: Ref<string>
  runningOnly: Ref<boolean>
  viewMode?: Ref<ViewMode>
}

const toSingle = (value: unknown): string => {
  if (Array.isArray(value)) return String(value[0] ?? '')
  return String(value ?? '')
}

const toPositiveInt = (value: unknown, fallback: number): number => {
  const parsed = Number.parseInt(toSingle(value), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

const normalizeAnalysisFilter = (value: unknown): AnalysisFilter => {
  const normalized = toSingle(value)
  return normalized === 'analyzed' || normalized === 'not_analyzed' ? normalized : 'all'
}

const normalizeReviewStatus = (value: unknown): ReviewStatus => {
  const normalized = toSingle(value)
  if (normalized === 'unreviewed' || normalized === 'reviewed' || normalized === 'needs_review') {
    return normalized
  }
  return 'all'
}

const normalizeViewMode = (value: unknown): ViewMode => {
  return toSingle(value) === 'cards' ? 'cards' : 'table'
}

const hasDateLikeFormat = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value)
const toBoolFlag = (value: unknown): boolean => {
  const normalized = toSingle(value).trim().toLowerCase()
  return normalized === "1" || normalized === "true" || normalized === "yes"
}

const applyQueryToRefs = (query: LocationQuery, refs: RouteStateRefs) => {
  refs.page.value = toPositiveInt(query.page, 1)
  refs.pageSize.value = toPositiveInt(query.page_size, 20)
  refs.ordering.value = toSingle(query.ordering) || '-date'
  refs.selectedTag.value = toSingle(query.tag)
  refs.selectedCorrespondent.value = toSingle(query.correspondent)
  refs.selectedReviewStatus.value = normalizeReviewStatus(query.review_status)
  refs.analysisFilter.value = normalizeAnalysisFilter(query.analysis_filter)
  refs.modelFilter.value = toSingle(query.model)
  refs.searchQuery.value = toSingle(query.q)
  refs.runningOnly.value = toBoolFlag(query.running_only)
  if (refs.viewMode) refs.viewMode.value = normalizeViewMode(query.view)

  const dateFrom = toSingle(query.date_from)
  const dateTo = toSingle(query.date_to)
  refs.dateFrom.value = hasDateLikeFormat(dateFrom) ? dateFrom : ''
  refs.dateTo.value = hasDateLikeFormat(dateTo) ? dateTo : ''
}

const buildQueryFromRefs = (refs: RouteStateRefs) => {
  const query: Record<string, string> = {}
  if (refs.page.value > 1) query.page = String(refs.page.value)
  if (refs.pageSize.value !== 20) query.page_size = String(refs.pageSize.value)
  if (refs.ordering.value !== '-date') query.ordering = refs.ordering.value
  if (refs.selectedTag.value) query.tag = refs.selectedTag.value
  if (refs.selectedCorrespondent.value) query.correspondent = refs.selectedCorrespondent.value
  if (refs.selectedReviewStatus.value !== 'all') query.review_status = refs.selectedReviewStatus.value
  if (refs.analysisFilter.value !== 'all') query.analysis_filter = refs.analysisFilter.value
  if (refs.modelFilter.value.trim()) query.model = refs.modelFilter.value.trim()
  if (refs.searchQuery.value.trim()) query.q = refs.searchQuery.value.trim()
  if (refs.runningOnly.value) query.running_only = "1"
  if (refs.viewMode?.value === 'cards') query.view = 'cards'
  if (refs.dateFrom.value) query.date_from = refs.dateFrom.value
  if (refs.dateTo.value) query.date_to = refs.dateTo.value
  return query
}

const normalizeQueryForCompare = (query: LocationQuery): Record<string, string> => {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(query)) {
    const single = toSingle(value)
    if (single) out[key] = single
  }
  return out
}

const areFlatQueriesEqual = (left: Record<string, string>, right: Record<string, string>): boolean => {
  const leftKeys = Object.keys(left)
  const rightKeys = Object.keys(right)
  if (leftKeys.length !== rightKeys.length) return false
  for (const key of leftKeys) {
    if (left[key] !== right[key]) return false
  }
  return true
}

export const useDocumentsRouteState = (refs: RouteStateRefs) => {
  const route = useRoute()
  const router = useRouter()
  const ready = ref(false)
  const syncing = ref(false)

  onMounted(() => {
    applyQueryToRefs(route.query, refs)
    ready.value = true
  })

  watch(
    () => route.query,
    (query) => {
      if (!ready.value || syncing.value) return
      applyQueryToRefs(query, refs)
    },
  )

  const watchedRefs: Array<Ref<unknown>> = [
    refs.page,
    refs.pageSize,
    refs.ordering,
    refs.selectedTag,
    refs.selectedCorrespondent,
    refs.selectedReviewStatus,
    refs.dateFrom,
    refs.dateTo,
    refs.analysisFilter,
    refs.modelFilter,
    refs.searchQuery,
    refs.runningOnly,
  ]
  if (refs.viewMode) watchedRefs.push(refs.viewMode)

  watch(
    watchedRefs,
    async () => {
      if (!ready.value) return
      const nextQuery = buildQueryFromRefs(refs)
      const currentQuery = normalizeQueryForCompare(route.query)
      if (areFlatQueriesEqual(currentQuery, nextQuery)) return
      syncing.value = true
      try {
        await router.replace({ path: route.path, query: nextQuery })
      } finally {
        syncing.value = false
      }
    },
  )
}
