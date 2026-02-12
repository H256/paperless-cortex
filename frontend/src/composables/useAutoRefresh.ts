import { onBeforeUnmount, watch, type Ref } from 'vue'

type AutoRefreshOptions = {
  enabled: Ref<boolean>
  onTick: () => void | Promise<void>
  intervalMs?: number
}

export const useAutoRefresh = ({ enabled, onTick, intervalMs = 5000 }: AutoRefreshOptions) => {
  let timer: ReturnType<typeof setInterval> | null = null
  let running = false

  const clearTimer = () => {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  const tick = async () => {
    if (running) return
    running = true
    try {
      await onTick()
    } finally {
      running = false
    }
  }

  watch(
    enabled,
    (active) => {
      if (!active) {
        clearTimer()
        return
      }
      if (timer !== null) return
      timer = setInterval(() => {
        void tick()
      }, intervalMs)
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    clearTimer()
  })
}
