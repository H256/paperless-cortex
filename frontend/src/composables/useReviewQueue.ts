import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { listDocuments } from '../services/documents'
import { prefetchDocument, prefetchSuggestions } from '../services/prefetchCache'
import {
  isTypingTarget,
  loadReviewQueueState,
  readAutoAdvance,
  reviewQueuePosition,
  saveReviewQueueState,
  writeAutoAdvance,
  type ReviewQueueState,
} from '../utils/reviewQueue'
import {
  canExtendNext,
  canExtendPrev,
  extendReviewQueueNext,
  extendReviewQueuePrev,
  type FetchReviewPage,
} from '../utils/reviewQueuePaging'

type Options = {
  fetchPage?: FetchReviewPage
  prefetchDocument?: (id: number) => void
  prefetchSuggestions?: (id: number) => void
  /** Delay before the next document is requested ahead of time. */
  prefetchDelayMs?: number
  /** Load further documents when at most this many are left in the queue. */
  lookahead?: number
}

const defaultFetchPage: FetchReviewPage = (params) =>
  listDocuments(params) as unknown as ReturnType<FetchReviewPage>

/**
 * Previous/next navigation inside the list the document was opened from.
 * The documents list remembers the visible ids together with the list request, so the
 * queue can continue on further pages. Without a remembered list the controls stay hidden.
 */
export const useReviewQueue = (
  docId: Ref<number>,
  route: RouteLocationNormalizedLoaded,
  router: Router,
  options: Options = {},
) => {
  const fetchPage = options.fetchPage ?? defaultFetchPage
  const doPrefetchDocument = options.prefetchDocument ?? prefetchDocument
  const doPrefetchSuggestions = options.prefetchSuggestions ?? prefetchSuggestions
  const prefetchDelayMs = options.prefetchDelayMs ?? 600
  const lookahead = options.lookahead ?? 2

  const state = ref<ReviewQueueState | null>(loadReviewQueueState())
  const autoAdvance = ref(readAutoAdvance())
  const loadingMore = ref(false)

  const ids = computed(() => state.value?.ids ?? [])
  const position = computed(() => reviewQueuePosition(ids.value, docId.value))
  const hasQueue = computed(() => position.value !== null && ids.value.length > 1)
  const canLoadNext = computed(() => (state.value ? canExtendNext(state.value) : false))
  const canLoadPrev = computed(() => (state.value ? canExtendPrev(state.value) : false))
  const hasNext = computed(() => position.value?.nextId != null || canLoadNext.value)
  const hasPrev = computed(() => position.value?.prevId != null || canLoadPrev.value)

  const persist = (next: ReviewQueueState) => {
    state.value = next
    saveReviewQueueState(next)
  }

  let extending: Promise<void> | null = null
  const extend = async (direction: 'next' | 'prev') => {
    if (extending) return extending
    const current = state.value
    if (!current) return undefined
    extending = (async () => {
      loadingMore.value = true
      try {
        let next = current
        // A previous page can consist of filtered-out rows only, so look a bit further.
        for (let attempt = 0; attempt < 3; attempt += 1) {
          const before = next.ids.length
          next =
            direction === 'next'
              ? await extendReviewQueueNext(next, fetchPage)
              : await extendReviewQueuePrev(next, fetchPage)
          if (next.ids.length > before) break
          if (direction === 'next' || !canExtendPrev(next)) break
        }
        if (next !== current) persist(next)
      } catch {
        // Keep the loaded part usable; the next navigation retries.
      } finally {
        loadingMore.value = false
        extending = null
      }
    })()
    return extending
  }

  const open = async (id: number | null) => {
    if (id === null) return
    // Keep return_to and the active tab so the reviewer stays in the same view.
    await router.push({ path: `/documents/${id}`, query: { ...route.query } })
  }

  const goNext = async () => {
    if (position.value?.nextId == null && canLoadNext.value) await extend('next')
    await open(position.value?.nextId ?? null)
  }

  const goPrev = async () => {
    if (position.value?.prevId == null && canLoadPrev.value) await extend('prev')
    await open(position.value?.prevId ?? null)
  }

  /** Jump to the next document after a document became reviewed (setting-controlled). */
  const advanceAfterReview = async () => {
    if (!autoAdvance.value || !hasQueue.value) return false
    if (position.value?.nextId == null && canLoadNext.value) await extend('next')
    const next = position.value?.nextId ?? null
    if (next === null) return false
    await open(next)
    return true
  }

  const onKeydown = (event: KeyboardEvent) => {
    if (event.ctrlKey || event.metaKey || event.altKey || isTypingTarget(event.target)) return
    if (!hasQueue.value) return
    if (event.key === 'j') {
      event.preventDefault()
      void goNext()
    } else if (event.key === 'k') {
      event.preventDefault()
      void goPrev()
    }
  }

  let prefetchTimer: ReturnType<typeof setTimeout> | null = null
  const clearPrefetchTimer = () => {
    if (prefetchTimer) {
      clearTimeout(prefetchTimer)
      prefetchTimer = null
    }
  }

  const schedulePrefetch = () => {
    clearPrefetchTimer()
    const nextId = position.value?.nextId ?? null
    if (nextId === null) return
    prefetchTimer = setTimeout(() => {
      prefetchTimer = null
      doPrefetchDocument(nextId)
      // Suggestions are only requested ahead of time when they already exist, so
      // prefetching never triggers generation for documents that are not opened.
      if (state.value?.suggestionIds.includes(nextId)) doPrefetchSuggestions(nextId)
    }, prefetchDelayMs)
  }

  const ensureLookahead = () => {
    const pos = position.value
    if (!pos || !canLoadNext.value || loadingMore.value) return
    if (pos.total - 1 - pos.index <= lookahead) void extend('next')
  }

  watch(autoAdvance, (value) => writeAutoAdvance(value))
  watch(
    () => docId.value,
    () => {
      // Another tab may have stored a newer list that still contains this document.
      const stored = loadReviewQueueState()
      if (stored && stored.ids.includes(docId.value) && stored.savedAt > (state.value?.savedAt ?? 0)) {
        state.value = stored
      }
    },
  )
  watch(
    [() => docId.value, () => position.value?.nextId, () => state.value?.ids.length],
    () => {
      schedulePrefetch()
      ensureLookahead()
    },
    { immediate: true },
  )

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeydown)
    clearPrefetchTimer()
  })

  return {
    position,
    hasQueue,
    hasNext,
    hasPrev,
    loadingMore,
    autoAdvance,
    goPrev,
    goNext,
    advanceAfterReview,
  }
}
