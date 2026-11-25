import { defineStore } from 'pinia'

export type ToastTone = 'info' | 'success' | 'warning' | 'danger'

export type ToastItem = {
  id: string
  title?: string
  message: string
  tone: ToastTone
  count: number
}

const MAX_VISIBLE_TOASTS = 3
const timers = new Map<string, number>()

export const useToastStore = defineStore('toasts', {
  state: () => ({
    toasts: [] as ToastItem[],
  }),
  actions: {
    push(message: string, tone: ToastTone = 'info', title?: string, durationMs = 1400) {
      const existing = this.toasts.find(
        (toast) => toast.message === message && toast.tone === tone && toast.title === title,
      )
      const id = existing?.id ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
      if (existing) {
        existing.count += 1
        window.clearTimeout(timers.get(id))
      } else {
        this.toasts.push({ id, message, tone, title, count: 1 })
        while (this.toasts.length > MAX_VISIBLE_TOASTS) this.remove(this.toasts[0]!.id)
      }
      timers.set(
        id,
        window.setTimeout(() => {
          this.remove(id)
        }, durationMs),
      )
    },
    remove(id: string) {
      window.clearTimeout(timers.get(id))
      timers.delete(id)
      this.toasts = this.toasts.filter((toast) => toast.id !== id)
    },
  },
})
