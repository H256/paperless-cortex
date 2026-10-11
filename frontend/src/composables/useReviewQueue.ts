import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import {
  isTypingTarget,
  loadReviewQueue,
  readAutoAdvance,
  reviewQueuePosition,
  writeAutoAdvance,
} from '../utils/reviewQueue'

/**
 * Previous/next navigation inside the list the document was opened from.
 * The list is remembered by the documents view; without it the controls stay hidden.
 */
export const useReviewQueue = (
  docId: Ref<number>,
  route: RouteLocationNormalizedLoaded,
  router: Router,
) => {
  const ids = ref<number[]>(loadReviewQueue())
  const autoAdvance = ref(readAutoAdvance())

  const position = computed(() => reviewQueuePosition(ids.value, docId.value))
  const hasQueue = computed(() => position.value !== null && ids.value.length > 1)

  const open = async (id: number | null) => {
    if (id === null) return
    // Keep return_to and the active tab so the reviewer stays in the same view.
    await router.push({ path: `/documents/${id}`, query: { ...route.query } })
  }

  const goPrev = async () => open(position.value?.prevId ?? null)
  const goNext = async () => open(position.value?.nextId ?? null)

  /** Jump to the next document after a document became reviewed (setting-controlled). */
  const advanceAfterReview = async () => {
    if (!autoAdvance.value || !hasQueue.value) return false
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

  watch(autoAdvance, (value) => writeAutoAdvance(value))
  watch(
    () => docId.value,
    () => {
      // Another tab may have stored a newer list.
      const stored = loadReviewQueue()
      if (stored.includes(docId.value)) ids.value = stored
    },
  )

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

  return { position, hasQueue, autoAdvance, goPrev, goNext, advanceAfterReview }
}
