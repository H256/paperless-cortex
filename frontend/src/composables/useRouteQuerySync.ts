import { ref, watch, type WatchSource } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { isSameQueryState } from '../utils/queryState'

type Options = {
  route: RouteLocationNormalizedLoaded
  router: Router
  readFromRoute: () => void
  buildQuery: () => Record<string, string>
  sources: WatchSource<unknown>[]
  debounceMs?: number
  preserveUnknownQueryKeys?: boolean
}

export const useRouteQuerySync = (options: Options) => {
  const syncingFromRoute = ref(false)
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  const syncFromRoute = () => {
    syncingFromRoute.value = true
    options.readFromRoute()
    syncingFromRoute.value = false
  }

  const syncToRoute = async () => {
    const managed = options.buildQuery()
    const next: Record<string, string> = options.preserveUnknownQueryKeys
      ? Object.fromEntries(
          Object.entries(options.route.query)
            .map(([key, value]) => [key, Array.isArray(value) ? value[0] : value])
            .filter(([, value]) => typeof value === 'string')
            .map(([key, value]) => [key, value as string]),
        )
      : {}
    Object.assign(next, managed)
    Object.keys(next).forEach((key) => {
      const value = next[key]
      if (value === '') delete next[key]
    })
    if (isSameQueryState(options.route.query, next)) return
    await options.router.replace({ query: next })
  }

  const queueSyncToRoute = () => {
    const debounceMs = Number(options.debounceMs || 0)
    if (debounceMs <= 0) {
      void syncToRoute()
      return
    }
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      void syncToRoute()
    }, debounceMs)
  }

  watch(options.sources, () => {
    if (syncingFromRoute.value) return
    queueSyncToRoute()
  })

  watch(
    () => options.route.query,
    () => {
      syncFromRoute()
    },
  )

  return {
    syncingFromRoute,
    syncFromRoute,
    syncToRoute,
    queueSyncToRoute,
  }
}
