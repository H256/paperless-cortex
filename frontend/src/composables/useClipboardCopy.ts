const errorMessage = (err: unknown) => {
  if (err instanceof Error) return err.message || 'Copy failed'
  if (typeof err === 'string') return err || 'Copy failed'
  return 'Copy failed'
}

export const useClipboardCopy = () => {
  const copyText = async (value: string) => {
    await navigator.clipboard.writeText(value)
  }

  return {
    copyText,
    errorMessage,
  }
}

