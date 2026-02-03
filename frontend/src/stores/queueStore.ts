import { defineStore } from 'pinia'
import {
  type QueuePeekItem,
  type QueueStatus,
  clearQueue,
  fetchQueuePeek,
  fetchQueueStatus,
  resetQueueStats,
  pauseQueue,
  resumeQueue,
  moveQueueItem,
  moveQueueItemTop,
  moveQueueItemBottom,
  removeQueueItem,
} from '../services/queue'

export const useQueueStore = defineStore('queue', {
  state: () => ({
    status: { enabled: false, length: null } as QueueStatus,
    peekItems: [] as QueuePeekItem[],
    peekLimit: 20,
    error: '',
    loading: false,
    peekLoading: false,
  }),
  actions: {
    async refreshStatus() {
      try {
        this.loading = true
        this.status = await fetchQueueStatus()
      } catch {
        this.status = { enabled: false, length: null }
      } finally {
        this.loading = false
      }
    },
    async loadPeek() {
      this.error = ''
      try {
        this.peekLoading = true
        const data = await fetchQueuePeek(this.peekLimit)
        this.peekItems = data.items ?? []
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load queue items'
        this.error = message || 'Failed to load queue items'
      } finally {
        this.peekLoading = false
      }
    },
    async clear() {
      await clearQueue()
      await this.refreshStatus()
      await this.loadPeek()
    },
    async resetStats() {
      await resetQueueStats()
      await this.refreshStatus()
    },
    async pause() {
      await pauseQueue()
      await this.refreshStatus()
    },
    async resume() {
      await resumeQueue()
      await this.refreshStatus()
    },
    async move(fromIndex: number, toIndex: number) {
      await moveQueueItem({ from_index: fromIndex, to_index: toIndex })
      await this.loadPeek()
    },
    async moveTop(index: number) {
      await moveQueueItemTop({ index })
      await this.loadPeek()
    },
    async moveBottom(index: number) {
      await moveQueueItemBottom({ index })
      await this.loadPeek()
    },
    async remove(index: number) {
      await removeQueueItem({ index })
      await this.loadPeek()
      await this.refreshStatus()
    },
  },
})
