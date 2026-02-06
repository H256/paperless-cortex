<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Metadata</div>
    <dl class="mt-3 grid gap-3 md:grid-cols-3">
      <div
        v-for="row in rows"
        :key="row.label"
        class="rounded-lg border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-800"
      >
        <dt class="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          {{ row.label }}
        </dt>
        <dd class="mt-1 text-sm text-slate-900 break-words dark:text-slate-100">
          <template v-if="row.label === 'Notes'">
            <details class="group">
              <summary class="cursor-pointer text-xs font-semibold text-slate-500">
                Show notes
              </summary>
              <div
                v-if="row.value"
                class="mt-2 whitespace-pre-wrap text-sm text-slate-900 dark:text-slate-100"
              >
                {{ row.value }}
              </div>
              <div v-else class="mt-2 text-xs text-slate-400">No notes</div>
            </details>
          </template>
          <template v-else>
            <span v-if="row.value !== null && row.value !== undefined && row.value !== ''">{{
              row.value
            }}</span>
            <span v-else class="text-xs text-slate-400">-</span>
          </template>
        </dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
type MetadataRow = {
  label: string
  value: string | number | null | undefined
}

defineProps<{
  rows: MetadataRow[]
}>()
</script>
