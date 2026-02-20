<template>
  <div
    class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">{{ title }}</h3>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
      {{ description }}
    </p>
    <div class="mt-4 flex items-center gap-3">
      <button
        class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
        :disabled="loading"
        @click="$emit('action')"
      >
        <span v-if="loading" class="inline-flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          {{ loadingLabel }}
        </span>
        <span v-else>{{ actionLabel }}</span>
      </button>
      <div v-if="resultText" class="text-xs text-slate-500 dark:text-slate-400">
        {{ resultText }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'

defineProps<{
  title: string
  description: string
  actionLabel: string
  loadingLabel: string
  loading: boolean
  resultText?: string
}>()

defineEmits<{
  action: []
}>()
</script>
