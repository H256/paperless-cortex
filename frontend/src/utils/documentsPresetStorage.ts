// Remembers the last applied documents-list preset across page reloads.
// The value is a preset key (e.g. "unreviewed"); an empty string means "none".

const STORAGE_KEY = 'documents.lastPreset'

export type PresetKey =
  | 'unreviewed'
  | 'needs_review'
  | 'not_analyzed'
  | 'inbox'
  | 'no_correspondent'
  | 'import_date'

const PRESET_KEYS: ReadonlySet<string> = new Set<PresetKey>([
  'unreviewed',
  'needs_review',
  'not_analyzed',
  'inbox',
  'no_correspondent',
  'import_date',
])

const safeStorage = (): Storage | null => {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export const readLastPreset = (): PresetKey | '' => {
  const storage = safeStorage()
  if (!storage) return ''
  try {
    const value = storage.getItem(STORAGE_KEY) ?? ''
    return PRESET_KEYS.has(value) ? (value as PresetKey) : ''
  } catch {
    return ''
  }
}

export const writeLastPreset = (key: PresetKey): void => {
  const storage = safeStorage()
  if (!storage) return
  try {
    storage.setItem(STORAGE_KEY, PRESET_KEYS.has(key) ? key : '')
  } catch {
    // localStorage can be unavailable (private mode / quota); remember is best-effort.
  }
}

export const clearLastPreset = (): void => {
  const storage = safeStorage()
  if (!storage) return
  try {
    storage.removeItem(STORAGE_KEY)
  } catch {
    // best-effort
  }
}
