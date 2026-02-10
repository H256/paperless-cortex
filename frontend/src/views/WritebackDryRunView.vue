<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Writeback Dry-Run (PoC)
        </h2>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          Shows which Paperless API calls would run. No data is written.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <label class="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <input type="checkbox" v-model="onlyChanged" />
          Changed documents only
        </label>
        <button
          class="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
          :disabled="loading"
          @click="loadPreview"
        >
          {{ loading ? 'Loading...' : 'Reload' }}
        </button>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
      <button
        class="rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
        @click="selectAllChanged"
      >
        Select all changed
      </button>
      <button
        class="rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
        @click="clearSelection"
      >
        Clear selection
      </button>
      <button
        class="rounded-md bg-emerald-600 px-3 py-1 font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
        :disabled="running || selectedIds.length === 0"
        @click="runDryRun"
      >
        {{ running ? 'Running dry-run...' : `Dry-run for ${selectedIds.length} document(s)` }}
      </button>
    </div>

    <div v-if="errorMessage" class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-200">
      {{ errorMessage }}
    </div>

    <div class="space-y-3">
      <article
        v-for="item in items"
        :key="item.doc_id"
        class="rounded-xl border bg-white p-4 shadow-sm dark:bg-slate-900"
        :class="item.changed ? 'border-amber-300 dark:border-amber-700/50' : 'border-slate-200 dark:border-slate-800'"
      >
        <div class="mb-3 flex items-center justify-between gap-3">
          <label class="inline-flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
            <input
              type="checkbox"
              :disabled="!item.changed"
              :checked="selectedSet.has(item.doc_id)"
              @change="toggleSelect(item.doc_id)"
            />
            Document {{ item.doc_id }}
          </label>
          <span
            class="rounded-full px-2 py-1 text-[11px] font-semibold"
            :class="item.changed ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200'"
          >
            {{ item.changed ? `changed: ${item.changed_fields.join(', ')}` : 'no changes' }}
          </span>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full text-xs">
            <thead>
              <tr class="text-left text-slate-500 dark:text-slate-400">
                <th class="px-2 py-1">Field</th>
                <th class="px-2 py-1">Original</th>
                <th class="px-2 py-1">New</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rowsFor(item)" :key="row.field" :class="row.changed ? 'bg-amber-50/70 dark:bg-amber-900/10' : ''">
                <td class="px-2 py-1 font-semibold text-slate-700 dark:text-slate-300">{{ row.field }}</td>
                <td class="px-2 py-1 text-slate-700 dark:text-slate-200 whitespace-pre-wrap">{{ displayValue(row.field, row.original, row.changed, 'original') }}</td>
                <td
                  class="px-2 py-1 whitespace-pre-wrap"
                  :class="row.changed ? 'font-semibold text-amber-800 dark:text-amber-200' : 'text-slate-400 dark:text-slate-500'"
                >
                  {{ displayValue(row.field, row.proposed, row.changed, 'proposed') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </div>

    <section
      v-if="dryRunResult"
      class="rounded-xl border border-slate-200 bg-white p-4 text-xs shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100">Dry-Run Result</h3>
      <p class="mt-1 text-slate-600 dark:text-slate-300">
        Selected: {{ dryRunResult.docs_selected }}, changed: {{ dryRunResult.docs_changed }},
        planned calls: {{ dryRunResult.calls.length }}
      </p>
      <pre class="mt-2 max-h-72 overflow-auto rounded bg-slate-100 p-3 text-[11px] dark:bg-slate-950">{{ JSON.stringify(dryRunResult.calls, null, 2) }}</pre>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getWritebackDryRunPreview,
  runWritebackDryRun,
  type WritebackDryRunExecuteResponse,
  type WritebackDryRunItem,
} from '../services/writeback'

const items = ref<WritebackDryRunItem[]>([])
const loading = ref(false)
const running = ref(false)
const onlyChanged = ref(true)
const selectedSet = ref<Set<number>>(new Set())
const errorMessage = ref('')
const dryRunResult = ref<WritebackDryRunExecuteResponse | null>(null)

const selectedIds = computed(() => Array.from(selectedSet.value))

const rowsFor = (item: WritebackDryRunItem) => [
  item.title,
  item.document_date,
  item.correspondent,
  item.tags,
  item.note,
]

const noteText = (value: unknown) => {
  if (!value || typeof value !== 'object') return ''
  const text = (value as { text?: unknown }).text
  return typeof text === 'string' ? text : ''
}

const displayValue = (
  field: string,
  value: unknown,
  changed: boolean,
  side: 'original' | 'proposed',
) => {
  if (side === 'proposed' && !changed) return ''
  if (value === null || value === undefined || value === '') return '—'

  if (field === 'correspondent' && typeof value === 'object' && value !== null) {
    const v = value as { name?: unknown; id?: unknown }
    const name = typeof v.name === 'string' ? v.name : ''
    const id = typeof v.id === 'number' ? v.id : null
    if (name && id !== null) return `${name} (#${id})`
    if (name) return name
    if (id !== null) return `#${id}`
    return '—'
  }

  if (field === 'tags' && typeof value === 'object' && value !== null) {
    const v = value as { names?: unknown; ids?: unknown }
    const names = Array.isArray(v.names)
      ? v.names.map((entry) => String(entry).trim()).filter(Boolean)
      : []
    if (names.length) return names.join(', ')
    const ids = Array.isArray(v.ids) ? v.ids.map((entry) => String(entry).trim()).filter(Boolean) : []
    return ids.length ? ids.join(', ') : '—'
  }

  if (field === 'note') {
    if (typeof value === 'string') return value
    const extracted = noteText(value)
    if (extracted) return extracted
    if (typeof value === 'object' && value !== null) return '—'
  }

  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

const toggleSelect = (docId: number) => {
  const next = new Set(selectedSet.value)
  if (next.has(docId)) next.delete(docId)
  else next.add(docId)
  selectedSet.value = next
}

const selectAllChanged = () => {
  selectedSet.value = new Set(items.value.filter((item) => item.changed).map((item) => item.doc_id))
}

const clearSelection = () => {
  selectedSet.value = new Set()
}

const loadPreview = async () => {
  loading.value = true
  errorMessage.value = ''
  dryRunResult.value = null
  try {
    const data = await getWritebackDryRunPreview({
      page: 1,
      page_size: 100,
      only_changed: onlyChanged.value,
    })
    items.value = data.items || []
    selectAllChanged()
  } catch (err: unknown) {
    errorMessage.value = err instanceof Error ? err.message : 'Preview could not be loaded'
  } finally {
    loading.value = false
  }
}

const runDryRun = async () => {
  running.value = true
  errorMessage.value = ''
  try {
    dryRunResult.value = await runWritebackDryRun(selectedIds.value)
  } catch (err: unknown) {
    errorMessage.value = err instanceof Error ? err.message : 'Dry-run failed'
  } finally {
    running.value = false
  }
}

onMounted(loadPreview)
</script>

