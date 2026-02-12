import type { QueryClient } from '@tanstack/vue-query'
import type { Store } from 'pinia'
import type { HealthStatus } from '../services/status'

type StatusStoreLike = Store & {
  applyStatus: (data: HealthStatus) => void
}

export const useStatusStream = (
  apiBaseUrl: string,
  statusStore: StatusStoreLike,
  queryClient: QueryClient,
) => {
  let statusStream: EventSource | null = null
  let statusStreamRetryId: number | null = null

  const stopStatusStream = () => {
    if (statusStream) {
      statusStream.close()
      statusStream = null
    }
    if (statusStreamRetryId !== null) {
      window.clearTimeout(statusStreamRetryId)
      statusStreamRetryId = null
    }
  }

  const startStatusStream = () => {
    stopStatusStream()
    const url = `${apiBaseUrl}/status/stream`
    statusStream = new EventSource(url)
    statusStream.onmessage = (event) => {
      if (!event?.data) return
      try {
        const payload = JSON.parse(event.data)
        if (payload?.status) {
          statusStore.applyStatus(payload.status)
          queryClient.setQueryData(['runtime-status'], payload.status)
        }
        if (payload?.queue) queryClient.setQueryData(['queue-status'], payload.queue)
        if (payload?.sync) queryClient.setQueryData(['sync-status'], payload.sync)
        if (payload?.embeddings) queryClient.setQueryData(['embed-status'], payload.embeddings)
        if (payload?.stats) queryClient.setQueryData(['documents-stats'], payload.stats)
      } catch {
        // ignore malformed payloads
      }
    }
    statusStream.onerror = () => {
      stopStatusStream()
      statusStreamRetryId = window.setTimeout(startStatusStream, 5000)
    }
  }

  return {
    startStatusStream,
    stopStatusStream,
  }
}
