<template>
  <div
    class="flex items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow-md"
    :class="toneClasses"
  >
    <div class="flex-1">
      <div class="font-semibold">{{ title }}</div>
      <div class="mt-1">{{ message }}</div>
    </div>
    <button
      class="text-xs font-semibold opacity-70 hover:opacity-100"
      @click="$emit('close')"
      aria-label="Dismiss toast"
    >
      ✕
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Tone = 'info' | 'success' | 'warning' | 'danger'

const props = withDefaults(
  defineProps<{
    title?: string
    message: string
    tone?: Tone
  }>(),
  {
    title: 'Notice',
    tone: 'info',
  },
)

const toneClasses = computed(() => {
  switch (props.tone) {
    case 'success':
      return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-200'
    case 'warning':
      return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-200'
    case 'danger':
      return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/40 dark:bg-rose-950/40 dark:text-rose-200'
    default:
      return 'border-slate-200 bg-white text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200'
  }
})
</script>
