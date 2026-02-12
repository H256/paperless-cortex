export const formatDateTime = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

export const formatRelativeTime = (value?: string | null) => {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  const diffSeconds = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000))
  if (diffSeconds < 60) return `${diffSeconds}s ago`
  const mins = Math.floor(diffSeconds / 60)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
