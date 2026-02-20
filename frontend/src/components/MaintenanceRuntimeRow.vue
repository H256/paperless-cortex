<template>
  <div class="flex items-center justify-between gap-4">
    <dt class="text-slate-500 dark:text-slate-400">{{ label }}</dt>
    <dd class="flex items-center gap-2 text-right text-slate-900 dark:text-slate-100">
      <span class="max-w-[220px] truncate">{{ displayValue }}</span>
      <button
        v-if="copyable"
        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        @click="$emit('copy')"
      >
        {{ copied ? 'Copied' : 'Copy' }}
      </button>
    </dd>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value?: string | number | null
  copyable?: boolean
  copied?: boolean
}>()

defineEmits<{
  copy: []
}>()

const displayValue = computed(() => {
  if (props.value === null || props.value === undefined || props.value === '') return '-'
  return String(props.value)
})
</script>
