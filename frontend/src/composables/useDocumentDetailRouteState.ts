import { computed, ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { consumeCitationJump } from '../services/citationJump'
import { parseBBox, queryToRecord, type BBox } from '../utils/documentDetail'

export type DetailTabKey =
  | 'meta'
  | 'text'
  | 'suggestions'
  | 'pages'
  | 'similar'
  | 'chat'
  | 'operations'

export const detailTabs: Array<{ key: DetailTabKey; label: string }> = [
  { key: 'meta', label: 'Metadata' },
  { key: 'text', label: 'Text & quality' },
  { key: 'suggestions', label: 'Suggestions' },
  { key: 'pages', label: 'Pages' },
  { key: 'similar', label: 'Similar' },
  { key: 'chat', label: 'Chat' },
  { key: 'operations', label: 'Operations' },
]

const normalizeTabQuery = (value: unknown): DetailTabKey => {
  const raw = Array.isArray(value) ? value[0] : value
  if (
    raw === 'text' ||
    raw === 'suggestions' ||
    raw === 'pages' ||
    raw === 'similar' ||
    raw === 'chat' ||
    raw === 'operations'
  ) {
    return raw
  }
  return 'meta'
}

export const useDocumentDetailRouteState = (
  route: RouteLocationNormalizedLoaded,
  router: Router,
) => {
  const returnToDocumentsPath = computed(() => {
    const raw = route.query.return_to
    const encoded = Array.isArray(raw) ? raw[0] : raw
    if (typeof encoded !== 'string' || !encoded.trim()) return '/documents'
    try {
      const decoded = decodeURIComponent(encoded)
      if (decoded.startsWith('/documents')) return decoded
    } catch {
      // ignore malformed return path
    }
    return '/documents'
  })

  const activeTab = ref<DetailTabKey>('meta')
  const pdfPage = ref(1)
  const pdfHighlights = ref<BBox[]>([])

  const syncPdfFromQuery = () => {
    const jump = consumeCitationJump(route.query.jump)
    if (route.query.jump !== undefined) {
      const nextQuery = queryToRecord(route.query, ['jump'])
      void router.replace({ query: nextQuery })
    }
    const pageValue = Number(jump?.page ?? route.query.page)
    if (Number.isFinite(pageValue) && pageValue > 0) {
      pdfPage.value = pageValue
    }
    const bbox = parseBBox(jump?.bbox ?? route.query.bbox)
    pdfHighlights.value = bbox ? [bbox] : []
  }

  const syncTabFromQuery = () => {
    activeTab.value = normalizeTabQuery(route.query.tab)
  }

  const syncTabToQuery = async () => {
    const current = normalizeTabQuery(route.query.tab)
    if (current === activeTab.value) return
    const nextQuery = queryToRecord(route.query)
    if (activeTab.value === 'meta') {
      delete nextQuery.tab
    } else {
      nextQuery.tab = activeTab.value
    }
    await router.replace({ query: nextQuery })
  }

  const onPdfPageChange = (value: number) => {
    pdfPage.value = value
    const nextQuery = queryToRecord(route.query)
    nextQuery.page = String(value)
    delete nextQuery.bbox
    void router.replace({ query: nextQuery })
    pdfHighlights.value = []
  }

  return {
    activeTab,
    pdfPage,
    pdfHighlights,
    returnToDocumentsPath,
    syncPdfFromQuery,
    syncTabFromQuery,
    syncTabToQuery,
    onPdfPageChange,
  }
}
