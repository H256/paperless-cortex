export type SuggestionApplyItem = {
  source: string
  field: string
  value: unknown
}

/**
 * Backend `apply-suggestion` replaces the whole tag set, so a subset of suggested
 * tags is merged with the existing and pending tags before it is sent.
 */
export const mergeTagNames = (...groups: Array<string[] | null | undefined>): string[] => {
  const seen = new Set<string>()
  const merged: string[] = []
  for (const group of groups) {
    for (const raw of group || []) {
      const name = String(raw).trim()
      const key = name.toLowerCase()
      if (!name || seen.has(key)) continue
      seen.add(key)
      merged.push(name)
    }
  }
  return merged
}

export const isPlainLeftClick = (event: MouseEvent) =>
  event.button === 0 && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)

export const isNewTabClick = (event: MouseEvent) =>
  event.button === 1 || (event.button === 0 && Boolean(event.metaKey || event.ctrlKey))
