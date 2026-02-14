import type { Ref } from 'vue'
import { onMounted, onUnmounted } from 'vue'

type Options = {
  inputRef: Ref<HTMLInputElement | null>
  onSubmit: () => unknown | Promise<unknown>
  focusKey?: string
  enableSubmitCombo?: boolean
}

export const useInputCommandHotkeys = (options: Options) => {
  const focusKey = options.focusKey ?? '/'
  const enableSubmitCombo = options.enableSubmitCombo ?? true

  const onWindowKeydown = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement | null
    const tag = target?.tagName?.toLowerCase()
    const isTypingTarget =
      tag === 'input' || tag === 'textarea' || target?.isContentEditable === true

    if (!isTypingTarget && event.key === focusKey) {
      event.preventDefault()
      options.inputRef.value?.focus()
      options.inputRef.value?.select()
      return
    }

    if (enableSubmitCombo && event.ctrlKey && event.key === 'Enter') {
      event.preventDefault()
      void options.onSubmit()
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', onWindowKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onWindowKeydown)
  })
}
