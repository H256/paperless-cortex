<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Metadata</div>
    <div v-if="statusCards?.length" class="mt-3 grid gap-3 md:grid-cols-2">
      <div
        v-for="card in statusCards"
        :key="card.label"
        class="rounded-lg border p-3"
        :class="cardToneClass(card.tone)"
      >
        <div class="text-[10px] font-semibold uppercase tracking-wide opacity-75">
          {{ card.label }}
        </div>
        <div class="mt-1 text-sm font-semibold">
          {{ card.value || '-' }}
        </div>
        <div v-if="card.subtext" class="mt-1 text-xs opacity-80">
          {{ card.subtext }}
        </div>
      </div>
    </div>
    <dl class="mt-3 grid gap-3 md:grid-cols-4">
      <div
        v-for="row in rows"
        :key="row.label"
        class="rounded-lg border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-800"
        :class="row.label === 'Notes' ? 'md:col-span-4' : ''"
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

type StatusCard = {
  label: string
  value: string | null | undefined
  subtext?: string | null
  tone?: 'neutral' | 'good' | 'warn'
}

const cardToneClass = (tone: StatusCard['tone']) => {
  if (tone === 'good') return 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-200'
  if (tone === 'warn') return 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200'
  return 'border-slate-200 bg-slate-50 text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100'
}

defineProps<{
  rows: MetadataRow[]
  statusCards?: StatusCard[]
}>()
</script>
