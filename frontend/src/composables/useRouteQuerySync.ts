import { ref, watch, type WatchSource } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { isSameQueryState } from '../utils/queryState'

type Options = {
  route: RouteLocationNormalizedLoaded
  router: Router
  readFromRoute: () => void
  buildQuery: () => Record<string, string>
  sources: WatchSource<unknown>[]
}

export const useRouteQuerySync = (options: Options) => {
  const syncingFromRoute = ref(false)

  const syncFromRoute = () => {
    syncingFromRoute.value = true
    options.readFromRoute()
    syncingFromRoute.value = false
  }

  const syncToRoute = async () => {
    const next = options.buildQuery()
    if (isSameQueryState(options.route.query, next)) return
    await options.router.replace({ query: next })
  }

  watch(options.sources, () => {
    if (syncingFromRoute.value) return
    void syncToRoute()
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
  }
}

