<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4"
  >
    <div
      class="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
    >
      <div class="text-base font-semibold text-slate-900 dark:text-slate-100">
        {{ title }}
      </div>
      <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">
        {{ message }}
      </p>
      <div class="mt-4 flex justify-end gap-2">
        <button
          class="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
          @click="$emit('cancel')"
        >
          {{ cancelLabel }}
        </button>
        <button
          class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
          @click="$emit('confirm')"
        >
          {{ confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
  }>(),
  {
    confirmLabel: 'Confirm',
    cancelLabel: 'Cancel',
  },
)

defineEmits<{ confirm: []; cancel: [] }>()
</script>
