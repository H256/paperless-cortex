import { defineStore } from 'pinia'

export interface AppError {
  id: string
  message: string
  detail?: string
  createdAt: number
  count: number
}

const MAX_VISIBLE_ERRORS = 3
const timers = new Map<string, number>()

const makeId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

export const useErrorStore = defineStore('errors', {
  state: () => ({
    errors: [] as AppError[],
  }),
  actions: {
    add(message: string, detail?: string, ttl = 6000) {
      const existing = this.errors.find((err) => err.message === message && err.detail === detail)
      const error: AppError = existing ?? { id: makeId(), message, detail, createdAt: Date.now(), count: 0 }
      error.count += 1
      error.createdAt = Date.now()
      if (existing) {
        window.clearTimeout(timers.get(error.id))
      } else {
        this.errors.unshift(error)
        this.errors.slice(MAX_VISIBLE_ERRORS).forEach((old) => this.remove(old.id))
      }
      if (ttl > 0) {
        timers.set(
          error.id,
          window.setTimeout(() => this.remove(error.id), ttl),
        )
      }
    },
    remove(id: string) {
      window.clearTimeout(timers.get(id))
      timers.delete(id)
      this.errors = this.errors.filter((err) => err.id !== id)
    },
    clear() {
      timers.forEach((timer) => window.clearTimeout(timer))
      timers.clear()
      this.errors = []
    },
  },
})
