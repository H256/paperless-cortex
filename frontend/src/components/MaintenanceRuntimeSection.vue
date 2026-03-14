<template>
  <section
    class="mt-6 rounded-xl border border-amber-200 bg-white p-6 shadow-sm dark:border-amber-900/50 dark:bg-slate-900"
  >
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h3 class="text-lg font-semibold text-amber-700 dark:text-amber-300">Worker lock</h3>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          Inspect Redis worker lock ownership and TTL. Reset only if a stale lock blocks startup.
        </p>
      </div>
      <button
        class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
        :disabled="workerLockLoading"
        @click="$emit('refresh-lock')"
      >
        <span v-if="workerLockLoading" class="inline-flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Refreshing...
        </span>
        <span v-else>Refresh lock status</span>
      </button>
    </div>
    <div
      class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
    >
      <div class="grid gap-2 md:grid-cols-3">
        <div>
          <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">State</div>
          <div class="font-semibold">
            {{ workerLockStatus?.has_lock ? 'Lock set' : 'No lock' }}
          </div>
        </div>
          <div>
            <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Owner</div>
            <div class="font-mono text-xs break-all">
              {{ workerLockStatus?.owner || '-' }}
            </div>
          </div>
        <div>
          <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">TTL</div>
          <div class="font-semibold">
            {{ workerLockStatusTtlLabel }}
          </div>
        </div>
      </div>
    </div>
    <div
      class="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
    >
      Resetting the lock may cause a currently running worker to stop on its next lock refresh.
    </div>
    <div class="mt-4 flex items-center gap-3">
      <button
        class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 hover:border-amber-300 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
        :disabled="workerLockResetLoading || !workerLockStatus?.has_lock"
        @click="$emit('reset-lock')"
      >
        <span v-if="workerLockResetLoading" class="inline-flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Resetting...
        </span>
        <span v-else>Reset worker lock</span>
      </button>
      <div v-if="workerLockResetResult" class="text-xs text-slate-500 dark:text-slate-400">
        {{ workerLockResetResult.had_lock ? 'Lock existed' : 'No lock existed' }},
        {{ workerLockResetResult.reset ? 'reset done' : 'nothing reset' }}.
        <span v-if="workerLockResetResult.reason">Reason: {{ workerLockResetResult.reason }}.</span>
      </div>
    </div>
  </section>

  <section
    class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Runtime Configuration
        </h3>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          Read-only view of server URLs and models currently in use.
        </p>
      </div>
    </div>
    <div class="mt-4 grid gap-4 md:grid-cols-2">
      <div
        class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
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
            label="LLM Base"
            :value="runtime.llm_base_url"
            :copyable="Boolean(runtime.llm_base_url)"
            :copied="copiedKey === 'llm_base'"
            @copy="$emit('copy-value', runtime.llm_base_url, 'llm_base')"
          />
          <MaintenanceRuntimeRow
            label="Qdrant"
            :value="runtime.qdrant_url"
            :copyable="Boolean(runtime.qdrant_url)"
            :copied="copiedKey === 'qdrant'"
            @copy="$emit('copy-value', runtime.qdrant_url, 'qdrant')"
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
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          Models
        </div>
        <dl class="mt-3 space-y-2">
          <MaintenanceRuntimeRow
            label="Text LLM"
            :value="runtime.text_model"
            :copyable="Boolean(runtime.text_model)"
            :copied="copiedKey === 'text_model'"
            @copy="$emit('copy-value', runtime.text_model, 'text_model')"
          />
          <MaintenanceRuntimeRow
            label="Chat LLM"
            :value="runtime.chat_model"
            :copyable="Boolean(runtime.chat_model)"
            :copied="copiedKey === 'chat_model'"
            @copy="$emit('copy-value', runtime.chat_model, 'chat_model')"
          />
          <MaintenanceRuntimeRow
            label="Embeddings"
            :value="runtime.embedding_model"
            :copyable="Boolean(runtime.embedding_model)"
            :copied="copiedKey === 'embedding_model'"
            @copy="$emit('copy-value', runtime.embedding_model, 'embedding_model')"
          />
          <MaintenanceRuntimeRow
            label="Vision OCR"
            :value="runtime.vision_model"
            :copyable="Boolean(runtime.vision_model)"
            :copied="copiedKey === 'vision_model'"
            @copy="$emit('copy-value', runtime.vision_model, 'vision_model')"
          />
          <MaintenanceRuntimeRow
            label="Evidence max pages"
            :value="runtime.evidence_max_pages"
          />
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
import { Loader2 } from 'lucide-vue-next'
import MaintenanceRuntimeRow from './MaintenanceRuntimeRow.vue'
import type { QueueWorkerLockReset, QueueWorkerLockStatus } from '../services/queue'

type MaintenanceRuntime = {
  paperless_base_url?: string | null
  llm_base_url?: string | null
  qdrant_url?: string | null
  redis_host?: string | null
  text_model?: string | null
  chat_model?: string | null
  embedding_model?: string | null
  vision_model?: string | null
  evidence_max_pages?: number | null
  evidence_min_snippet_chars?: number | null
}

defineProps<{
  runtime: MaintenanceRuntime
  copiedKey: string | null
  workerLockStatus: QueueWorkerLockStatus | null
  workerLockLoading: boolean
  workerLockResetLoading: boolean
  workerLockStatusTtlLabel: string
  workerLockResetResult: QueueWorkerLockReset | null
}>()

defineEmits<{
  (e: 'copy-value', value: string | null | undefined, key: string): void
  (e: 'refresh-lock'): void
  (e: 'reset-lock'): void
}>()
</script>
