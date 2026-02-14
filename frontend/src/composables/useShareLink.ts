import type { Router } from 'vue-router'
import { useToastStore } from '../stores/toastStore'
import { useClipboardCopy } from './useClipboardCopy'

type CopyOptions = {
  successMessage: string
  errorMessage?: string
  title?: string
  durationMs?: number
}

export const useShareLink = (router: Router, defaultTitle = 'Share') => {
  const toastStore = useToastStore()
  const { copyText, errorMessage } = useClipboardCopy()

  const copyResolvedLink = async (
    path: string,
    query: Record<string, string>,
    options: CopyOptions,
  ) => {
    try {
      const href = `${window.location.origin}${router.resolve({ path, query }).href}`
      await copyText(href)
      toastStore.push(
        options.successMessage,
        'success',
        options.title || defaultTitle,
        options.durationMs ?? 1600,
      )
    } catch (err) {
      toastStore.push(
        options.errorMessage || errorMessage(err),
        'danger',
        options.title || defaultTitle,
        options.durationMs ?? 2200,
      )
    }
  }

  const copyHrefLink = async (href: string, options: CopyOptions) => {
    if (!href) return
    try {
      await copyText(`${window.location.origin}${href}`)
      toastStore.push(
        options.successMessage,
        'success',
        options.title || defaultTitle,
        options.durationMs ?? 1600,
      )
    } catch (err) {
      toastStore.push(
        options.errorMessage || errorMessage(err),
        'danger',
        options.title || defaultTitle,
        options.durationMs ?? 2200,
      )
    }
  }

  return {
    copyResolvedLink,
    copyHrefLink,
  }
}

