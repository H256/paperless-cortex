export type ModelProviderRole = 'text' | 'chat' | 'embedding' | 'vision'

export type ModelProviderSettingsItem = {
  role: ModelProviderRole
  base_url: string | null
  model: string | null
  api_key_configured: boolean
  api_key_hint: string | null
  base_url_overridden: boolean
  model_overridden: boolean
  api_key_overridden: boolean
}

export type ModelProviderSettingsResponse = {
  items: ModelProviderSettingsItem[]
}

export type ModelProviderSettingsUpdateItem = {
  role: ModelProviderRole
  base_url?: string | null
  model?: string | null
  api_key?: string | null
  clear_api_key?: boolean
}

export type ModelProviderDiscoveryResult = {
  ok: boolean
  detail: string
  models: string[]
}

const parseJson = async (response: Response) => {
  const text = await response.text()
  return text ? JSON.parse(text) : {}
}

const request = async <T>(input: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(input, {
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  })
  const parsed = await parseJson(response)
  if (!response.ok) {
    const detail =
      typeof parsed?.detail === 'string'
        ? parsed.detail
        : typeof parsed?.error_code === 'string'
          ? parsed.error_code
          : `Request failed (${response.status})`
    throw new Error(detail)
  }
  return parsed as T
}

export const fetchModelProviderSettings = () =>
  request<ModelProviderSettingsResponse>('/api/settings/model-providers')

export const updateModelProviderSettings = (items: ModelProviderSettingsUpdateItem[]) =>
  request<ModelProviderSettingsResponse>('/api/settings/model-providers', {
    method: 'PUT',
    body: JSON.stringify({ items }),
  })

export const discoverProviderModels = (payload: {
  base_url: string | null
  api_key: string | null
}) =>
  request<ModelProviderDiscoveryResult>('/api/settings/model-providers/discover', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export type RuntimeConfiguration = {
  paperless_base_url?: string | null
  text_base_url?: string | null
  chat_base_url?: string | null
  embedding_base_url?: string | null
  vision_base_url?: string | null
  qdrant_url?: string | null
  vector_store_provider?: string | null
  vector_store_url?: string | null
  redis_host?: string | null
  text_model?: string | null
  chat_model?: string | null
  embedding_model?: string | null
  vision_model?: string | null
  evidence_max_pages?: number | null
  evidence_min_snippet_chars?: number | null
}
