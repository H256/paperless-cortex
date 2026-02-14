import { onMounted, onUnmounted } from 'vue'

type Handler = (event: KeyboardEvent) => void

export const useGlobalHotkeys = (handler: Handler) => {
  onMounted(() => {
    window.addEventListener('keydown', handler)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handler)
  })
}

