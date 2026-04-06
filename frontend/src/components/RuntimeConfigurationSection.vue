<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Runtime Configuration
        </h3>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          Effective server URLs and models currently in use.
        </p>
      </div>
    </div>
    <div class="mt-4 grid gap-4 md:grid-cols-2">
      <div
        class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
      >
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
          URLs
        </div>
        <dl class="mt-3 space-y-2">
          <MaintenanceRuntimeRow
            label="Paperless"
            :value="runtime.paperless_base_url"
            :copyable="Boolean(runtime.paperless_base_url)"
            :copied="copiedKey === 'paperless'"
            @copy="$emit('copy-value', runtime.paperless_base_url, 'paperless')"
          />
          <MaintenanceRuntimeRow
            label="Text LLM"
            :value="runtime.text_base_url"
            :copyable="Boolean(runtime.text_base_url)"
            :copied="copiedKey === 'text_base_url'"
            @copy="$emit('copy-value', runtime.text_base_url, 'text_base_url')"
          />
          <MaintenanceRuntimeRow
            label="Chat LLM"
            :value="runtime.chat_base_url"
            :copyable="Boolean(runtime.chat_base_url)"
            :copied="copiedKey === 'chat_base_url'"
            @copy="$emit('copy-value', runtime.chat_base_url, 'chat_base_url')"
          />
          <MaintenanceRuntimeRow
            label="Embedding LLM"
            :value="runtime.embedding_base_url"
            :copyable="Boolean(runtime.embedding_base_url)"
            :copied="copiedKey === 'embedding_base_url'"
            @copy="$emit('copy-value', runtime.embedding_base_url, 'embedding_base_url')"
          />
          <MaintenanceRuntimeRow
            label="Vision LLM"
            :value="runtime.vision_base_url"
            :copyable="Boolean(runtime.vision_base_url)"
            :copied="copiedKey === 'vision_base_url'"
            @copy="$emit('copy-value', runtime.vision_base_url, 'vision_base_url')"
          />
          <MaintenanceRuntimeRow
            label="Vector Store"
            :value="runtime.vector_store_url || runtime.qdrant_url"
            :copyable="Boolean(runtime.vector_store_url || runtime.qdrant_url)"
            :copied="copiedKey === 'vector_store_url'"
            @copy="$emit('copy-value', runtime.vector_store_url || runtime.qdrant_url, 'vector_store_url')"
          />
          <MaintenanceRuntimeRow
            label="Redis"
            :value="runtime.redis_host"
            :copyable="Boolean(runtime.redis_host)"
            :copied="copiedKey === 'redis'"
            @copy="$emit('copy-value', runtime.redis_host, 'redis')"
          />
        </dl>
      </div>
      <div
        class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
      >
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
          Models
        </div>
        <dl class="mt-3 space-y-2">
          <MaintenanceRuntimeRow label="Text LLM" :value="runtime.text_model" />
          <MaintenanceRuntimeRow label="Chat LLM" :value="runtime.chat_model" />
          <MaintenanceRuntimeRow label="Embeddings" :value="runtime.embedding_model" />
          <MaintenanceRuntimeRow label="Vision OCR" :value="runtime.vision_model" />
          <MaintenanceRuntimeRow label="Vector provider" :value="runtime.vector_store_provider" />
          <MaintenanceRuntimeRow label="Evidence max pages" :value="runtime.evidence_max_pages" />
          <MaintenanceRuntimeRow
            label="Evidence min snippet chars"
            :value="runtime.evidence_min_snippet_chars"
          />
        </dl>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { RuntimeConfiguration } from '../services/settings'
import MaintenanceRuntimeRow from './MaintenanceRuntimeRow.vue'

defineProps<{
  runtime: RuntimeConfiguration
  copiedKey: string | null
}>()

defineEmits<{
  (e: 'copy-value', value: string | null | undefined, key: string): void
}>()
</script>
