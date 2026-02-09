import { defineStore } from 'pinia'
import {
  type QueuePeekItem,
  type QueueRunningStatus,
  type QueueStatus,
  clearQueue,
  fetchQueuePeek,
  fetchQueueRunning,
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
    running: { enabled: false, task: null, started_at: null } as QueueRunningStatus,
    peekItems: [] as QueuePeekItem[],
    peekLimit: 20,
    error: '',
    loading: false,
    peekLoading: false,
  }),
  actions: {
    setStatus(status: QueueStatus) {
      this.status = status
    },
    async refreshStatus() {
      try {
        this.loading = true
        const [status, running] = await Promise.all([fetchQueueStatus(), fetchQueueRunning()])
        this.status = status
        this.running = running
      } catch {
        this.status = { enabled: false, length: null }
        this.running = { enabled: false, task: null, started_at: null }
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
