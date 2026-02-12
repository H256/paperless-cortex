import { defineStore } from 'pinia'
import {
  type QueueStatus,
  clearQueue,
  fetchQueueStatus,
} from '../services/queue'

export const useQueueStore = defineStore('queue', {
  state: () => ({
    status: { enabled: false, length: null } as QueueStatus,
    loading: false,
  }),
  actions: {
    setStatus(status: QueueStatus) {
      this.status = status
    },
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
    async clear() {
      await clearQueue()
      await this.refreshStatus()
    },
  },
})
