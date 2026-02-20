import { describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { useDocumentDetailRouteState } from './useDocumentDetailRouteState'

const createHarness = (query: Record<string, string> = {}) => {
  const route = reactive({
    query: { ...query },
  }) as unknown as Parameters<typeof useDocumentDetailRouteState>[0]
  const replace = vi.fn(async () => undefined)
  const router = { replace } as unknown as Parameters<typeof useDocumentDetailRouteState>[1]
  const state = useDocumentDetailRouteState(route, router)
  return { route, replace, state }
}

describe('useDocumentDetailRouteState', () => {
  it('resolves return path from encoded query', () => {
    const encoded = encodeURIComponent('/documents?page=2')
    const { state } = createHarness({ return_to: encoded })
    expect(state.returnToDocumentsPath.value).toBe('/documents?page=2')
  })

  it('falls back to /documents for invalid return path', () => {
    const encoded = encodeURIComponent('/queue')
    const { state } = createHarness({ return_to: encoded })
    expect(state.returnToDocumentsPath.value).toBe('/documents')
  })

  it('syncs tab state to and from query', async () => {
    const { state, replace, route } = createHarness({ tab: 'text', keep: '1' })
    state.syncTabFromQuery()
    expect(state.activeTab.value).toBe('text')

    state.activeTab.value = 'operations'
    await state.syncTabToQuery()
    expect(replace).toHaveBeenCalledWith({ query: { tab: 'operations', keep: '1' } })

    route.query = { tab: 'operations', keep: '1' }
    state.activeTab.value = 'meta'
    await state.syncTabToQuery()
    expect(replace).toHaveBeenLastCalledWith({ query: { keep: '1' } })
  })

  it('syncs page and bbox from query', () => {
    const { state, replace } = createHarness({ page: '7', bbox: '1,2,3,4', keep: '1' })
    state.syncPdfFromQuery()
    expect(state.pdfPage.value).toBe(7)
    expect(state.pdfHighlights.value).toEqual([[1, 2, 3, 4]])
    expect(replace).not.toHaveBeenCalled()
  })
})
