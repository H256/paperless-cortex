<template>
  <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">{{ title }}</h3>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">{{ description }}</p>
      </div>
      <span
        class="rounded-full px-2.5 py-1 text-[10px] font-semibold"
        :class="dirty ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-200' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200'"
      >
        {{ dirty ? 'Unsaved changes' : 'Saved' }}
      </span>
    </div>

    <div class="mt-4 grid gap-4 md:grid-cols-2">
      <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        URL
        <input
          :value="draft.base_url"
          type="text"
          class="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          placeholder="https://api.example.com"
          @input="$emit('update:base-url', ($event.target as HTMLInputElement).value)"
        />
      </label>

      <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Model
        <input
          :value="draft.model"
          :list="datalistId"
          type="text"
          class="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          placeholder="Choose or type a model"
          @input="$emit('update:model', ($event.target as HTMLInputElement).value)"
        />
        <datalist :id="datalistId">
          <option v-for="modelOption in models" :key="modelOption" :value="modelOption" />
        </datalist>
      </label>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-[1fr_auto]">
      <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        API Key
        <input
          :value="draft.api_key"
          type="password"
          class="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          :placeholder="apiKeyPlaceholder"
          autocomplete="new-password"
          @input="$emit('update:api-key', ($event.target as HTMLInputElement).value)"
        />
      </label>
      <div class="flex items-end gap-3">
        <button
          type="button"
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          :disabled="discoveryLoading"
          @click="$emit('discover')"
        >
          {{ discoveryLoading ? 'Refreshing...' : 'Refresh models' }}
        </button>
        <button
          type="button"
          class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
          @click="$emit('clear-api-key')"
        >
          Clear key
        </button>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap items-center gap-3 text-xs">
      <span class="text-slate-500 dark:text-slate-400">
        Stored key: {{ item.api_key_configured ? item.api_key_hint || 'configured' : 'not set' }}
      </span>
      <span
        v-if="discoveryMessage"
        :class="discoveryOk ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'"
      >
        {{ discoveryMessage }}
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ModelProviderSettingsItem, ModelProviderRole } from '../services/settings'

const props = defineProps<{
  role: ModelProviderRole
  title: string
  description: string
  item: ModelProviderSettingsItem
  draft: { base_url: string; model: string; api_key: string; clear_api_key: boolean }
  models: string[]
  dirty: boolean
  discoveryLoading: boolean
  discoveryMessage: string
  discoveryOk: boolean
}>()

defineEmits<{
  (e: 'discover'): void
  (e: 'clear-api-key'): void
  (e: 'update:base-url', value: string): void
  (e: 'update:model', value: string): void
  (e: 'update:api-key', value: string): void
}>()

const datalistId = computed(() => `models-${props.role}`)
const apiKeyPlaceholder = computed(() =>
  props.item.api_key_configured ? 'Leave empty to keep current key' : 'Paste API key',
)
</script>
