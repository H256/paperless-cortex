<template>
  <section>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Settings
        </h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Configure live model providers without restarting the containers.
        </p>
      </div>
      <button
        class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="!hasChanges || saveLoading"
        @click="saveChanges"
      >
        {{ saveLoading ? 'Saving...' : 'Save changes' }}
      </button>
    </div>

    <RuntimeConfigurationSection
      class="mt-6"
      :runtime="runtime"
      :copied-key="copiedKey"
      @copy-value="copyValue"
    />

    <section class="mt-6 grid gap-4 lg:grid-cols-2">
      <ModelProviderSettingsCard
        v-for="role in roleOrder"
        :key="role"
        :role="role"
        :title="roleMeta[role].title"
        :description="roleMeta[role].description"
        :item="providerByRole[role]"
        :draft="drafts[role]"
        :models="modelOptions[role]"
        :dirty="roleDirty(role)"
        :discovery-loading="discoveryLoading[role]"
        :discovery-message="discoveryMessage[role]"
        :discovery-ok="discoveryOk[role]"
        @discover="discover(role)"
        @clear-api-key="clearApiKey(role)"
        @update:base-url="drafts[role].base_url = $event"
        @update:model="drafts[role].model = $event"
        @update:api-key="drafts[role].api_key = $event"
      />
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import ModelProviderSettingsCard from '../components/ModelProviderSettingsCard.vue'
import RuntimeConfigurationSection from '../components/RuntimeConfigurationSection.vue'
import {
  discoverProviderModels,
  fetchModelProviderSettings,
  updateModelProviderSettings,
  type ModelProviderSettingsItem,
  type ModelProviderRole,
  type RuntimeConfiguration,
} from '../services/settings'
import { fetchHealthStatus } from '../services/status'
import { useToastStore } from '../stores/toastStore'

const toastStore = useToastStore()
const queryClient = useQueryClient()
const copiedKey = ref<string | null>(null)
const roleOrder: ModelProviderRole[] = ['text', 'chat', 'embedding', 'vision']

const roleMeta: Record<ModelProviderRole, { title: string; description: string }> = {
  text: {
    title: 'Text model',
    description: 'Used for suggestions, summaries, and other general text generation.',
  },
  chat: {
    title: 'Chat model',
    description: 'Used for interactive chat and follow-up generation.',
  },
  embedding: {
    title: 'Embedding model',
    description: 'Used for chunk embeddings, retrieval, and similarity indexing.',
  },
  vision: {
    title: 'Vision / OCR model',
    description: 'Used for image-based OCR and visual page understanding.',
  },
}

const settingsQuery = useQuery({
  queryKey: ['model-provider-settings'],
  queryFn: () => fetchModelProviderSettings(),
})

const runtimeQuery = useQuery({
  queryKey: ['runtime-status'],
  queryFn: () => fetchHealthStatus(),
  staleTime: 15_000,
})

const emptyItem = {
  role: 'text' as ModelProviderRole,
  base_url: null,
  model: null,
  api_key_configured: false,
  api_key_hint: null,
  base_url_overridden: false,
  model_overridden: false,
  api_key_overridden: false,
}

const providerByRole = computed(() => {
  const map: Record<ModelProviderRole, ModelProviderSettingsItem> = {
    text: { ...emptyItem, role: 'text' as const },
    chat: { ...emptyItem, role: 'chat' as const },
    embedding: { ...emptyItem, role: 'embedding' as const },
    vision: { ...emptyItem, role: 'vision' as const },
  }
  for (const item of settingsQuery.data.value?.items || []) {
    map[item.role] = item
  }
  return map
})

const drafts = reactive<Record<ModelProviderRole, { base_url: string; model: string; api_key: string; clear_api_key: boolean }>>({
  text: { base_url: '', model: '', api_key: '', clear_api_key: false },
  chat: { base_url: '', model: '', api_key: '', clear_api_key: false },
  embedding: { base_url: '', model: '', api_key: '', clear_api_key: false },
  vision: { base_url: '', model: '', api_key: '', clear_api_key: false },
})

watch(
  providerByRole,
  (value) => {
    for (const role of roleOrder) {
      drafts[role].base_url = value[role].base_url || ''
      drafts[role].model = value[role].model || ''
      drafts[role].api_key = ''
      drafts[role].clear_api_key = false
    }
  },
  { immediate: true },
)

const modelOptions = reactive<Record<ModelProviderRole, string[]>>({
  text: [],
  chat: [],
  embedding: [],
  vision: [],
})
const discoveryLoading = reactive<Record<ModelProviderRole, boolean>>({
  text: false,
  chat: false,
  embedding: false,
  vision: false,
})
const discoveryMessage = reactive<Record<ModelProviderRole, string>>({
  text: '',
  chat: '',
  embedding: '',
  vision: '',
})
const discoveryOk = reactive<Record<ModelProviderRole, boolean>>({
  text: false,
  chat: false,
  embedding: false,
  vision: false,
})
const saveLoading = ref(false)

const runtime = computed<RuntimeConfiguration>(() => ({
  paperless_base_url: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.paperless_base_url || '',
  text_base_url: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.text_base_url || '',
  chat_base_url: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.chat_base_url || '',
  embedding_base_url:
    (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.embedding_base_url || '',
  vision_base_url: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.vision_base_url || '',
  qdrant_url: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.qdrant_url || '',
  vector_store_provider:
    (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.vector_store_provider || '',
  vector_store_url:
    (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.vector_store_url || '',
  redis_host: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.redis_host || '',
  text_model: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.text_model || '',
  chat_model: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.chat_model || '',
  embedding_model:
    (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.embedding_model || '',
  vision_model: (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.vision_model || '',
  evidence_max_pages:
    (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.evidence_max_pages || 0,
  evidence_min_snippet_chars:
    (runtimeQuery.data.value as RuntimeConfiguration | undefined)?.evidence_min_snippet_chars || 0,
}))

const roleDirty = (role: ModelProviderRole) => {
  const item = providerByRole.value[role]
  const draft = drafts[role]
  return (
    (draft.base_url || '') !== (item.base_url || '') ||
    (draft.model || '') !== (item.model || '') ||
    draft.api_key.trim().length > 0 ||
    draft.clear_api_key
  )
}

const hasChanges = computed(() => roleOrder.some((role) => roleDirty(role)))

const discover = async (role: ModelProviderRole) => {
  discoveryLoading[role] = true
  discoveryMessage[role] = ''
  try {
    const result = await discoverProviderModels({
      base_url: drafts[role].base_url || null,
      api_key: drafts[role].api_key || null,
    })
    modelOptions[role] = result.models
    discoveryOk[role] = result.ok
    discoveryMessage[role] = result.ok ? `${result.models.length} models loaded` : result.detail
  } catch (err) {
    discoveryOk[role] = false
    discoveryMessage[role] = err instanceof Error ? err.message : 'Discovery failed'
  } finally {
    discoveryLoading[role] = false
  }
}

const clearApiKey = (role: ModelProviderRole) => {
  drafts[role].api_key = ''
  drafts[role].clear_api_key = true
}

const saveChanges = async () => {
  saveLoading.value = true
  try {
    const items = roleOrder
      .filter((role) => roleDirty(role))
      .map((role) => ({
        role,
        base_url: drafts[role].base_url.trim() || null,
        model: drafts[role].model.trim() || null,
        api_key: drafts[role].api_key.trim() || null,
        clear_api_key: drafts[role].clear_api_key,
      }))
    await updateModelProviderSettings(items)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['model-provider-settings'] }),
      queryClient.invalidateQueries({ queryKey: ['runtime-status'] }),
    ])
    await Promise.all([settingsQuery.refetch(), runtimeQuery.refetch()])
    toastStore.push('Live model settings saved', 'success', 'Settings updated')
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save settings'
    toastStore.push(message, 'danger', 'Error')
  } finally {
    saveLoading.value = false
  }
}

const copyValue = async (value: string | null | undefined, key: string) => {
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
    copiedKey.value = key
    window.setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = null
    }, 1200)
  } catch {
    copiedKey.value = null
  }
}

watch(
  () => settingsQuery.data.value?.items,
  async (items) => {
    if (!items?.length) return
    for (const role of roleOrder) {
      if (drafts[role].base_url) {
        await discover(role)
      }
    }
  },
  { immediate: true },
)
</script>
