<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Duplicates
        </h2>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          Likely duplicate documents, grouped. Detection tolerates OCR differences (download vs.
          scanned print-out).
        </p>
      </div>
      <button
        class="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
        :disabled="scanning"
        data-test="scan"
        @click="onScan"
      >
        {{ scanning ? 'Queueing...' : 'Scan for duplicates' }}
      </button>
    </div>

    <div
      class="flex flex-wrap items-center gap-2 overflow-x-auto rounded-xl border border-slate-200 bg-white p-2 text-xs font-semibold shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="inline-flex whitespace-nowrap rounded-lg px-3 py-1.5"
        :class="
          activeTab === tab.id
            ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
        "
        :data-test="`tab-${tab.id}`"
        @click="activeTab = tab.id"
      >
        {{ tab.label }} ({{ tab.id === 'groups' ? groups.length : ignored.length }})
      </button>
      <label
        v-if="activeTab === 'groups'"
        class="ml-auto inline-flex items-center gap-2 text-slate-600 dark:text-slate-300"
      >
        Min. confidence
        <select
          v-model="minLevel"
          class="rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="check">Check</option>
          <option value="likely">Likely</option>
          <option value="very_likely">Very likely</option>
        </select>
      </label>
    </div>

    <p v-if="error" class="text-sm text-rose-600 dark:text-rose-400">{{ error }}</p>
    <p v-else-if="loading" class="text-sm text-slate-500 dark:text-slate-400">Loading...</p>

    <template v-if="activeTab === 'groups'">
      <p v-if="!loading && !groups.length" class="text-sm text-slate-500 dark:text-slate-400">
        No duplicate groups. Run a scan after embeddings are available.
      </p>
      <article
        v-for="group in groups"
        :key="group.group_id"
        class="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        data-test="duplicate-group"
      >
        <header class="flex flex-wrap items-center gap-2">
          <span
            :class="levelClass(group.level)"
            class="rounded-full px-2 py-0.5 text-xs font-semibold"
          >
            {{ levelLabel(group.level) }}
          </span>
          <span class="text-xs text-slate-500 dark:text-slate-400">
            {{ group.doc_ids.length }} documents · best score {{ percent(group.best_score) }}
          </span>
        </header>

        <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <RouterLink
            v-for="doc in group.documents"
            :key="doc.id"
            :to="`/documents/${doc.id}`"
            class="rounded-lg border border-slate-200 p-3 text-sm hover:border-indigo-400 dark:border-slate-700"
          >
            <div class="font-medium text-slate-900 dark:text-slate-100">
              {{ doc.title || `Document ${doc.id}` }}
            </div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              #{{ doc.id }} · {{ doc.correspondent_name || 'no correspondent' }} ·
              {{ doc.document_date || doc.created?.slice(0, 10) || 'no date' }} ·
              {{ doc.page_count ?? '?' }} p.
            </div>
          </RouterLink>
        </div>

        <ul class="space-y-1">
          <li
            v-for="pair in group.pairs"
            :key="`${pair.doc_a_id}-${pair.doc_b_id}`"
            class="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300"
            data-test="duplicate-pair"
          >
            <span class="font-semibold">#{{ pair.doc_a_id }} ↔ #{{ pair.doc_b_id }}</span>
            <span>{{ percent(pair.score) }}</span>
            <span class="text-slate-400">
              emb {{ percent(pair.embedding_score) }} · text {{ percent(pair.text_score) }} · keys
              {{ percent(pair.keys_score) }} · meta {{ percent(pair.meta_score) }}
            </span>
            <span
              v-if="pair.signals?.key_conflict"
              class="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
            >
              amounts/numbers differ
            </span>
            <button
              class="ml-auto rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
              data-test="ignore-pair"
              @click="toggleIgnore(pair, true)"
            >
              Not a duplicate
            </button>
          </li>
        </ul>
      </article>
    </template>

    <template v-else>
      <p v-if="!loading && !ignored.length" class="text-sm text-slate-500 dark:text-slate-400">
        No ignored pairs.
      </p>
      <ul class="space-y-2">
        <li
          v-for="pair in ignored"
          :key="`${pair.doc_a_id}-${pair.doc_b_id}`"
          class="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-900"
          data-test="ignored-pair"
        >
          <span class="font-medium text-slate-900 dark:text-slate-100">
            <template v-for="(doc, idx) in pair.documents" :key="doc.id">
              <span v-if="idx"> ↔ </span>
              <RouterLink :to="`/documents/${doc.id}`" class="hover:underline">
                {{ doc.title || `Document ${doc.id}` }}
              </RouterLink>
            </template>
          </span>
          <span class="text-xs text-slate-500">{{ percent(pair.score) }}</span>
          <button
            class="ml-auto rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            data-test="unignore-pair"
            @click="toggleIgnore(pair, false)"
          >
            Restore
          </button>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useDuplicates, type DuplicateLevelFilter } from '../composables/useDuplicates'
import { useToastStore } from '../stores/toastStore'
import type { DuplicatePairOut } from '../api/generated/model'

const toastStore = useToastStore()
const { groups, ignored, loading, scanning, error, load, startScan, setIgnored } = useDuplicates()

const tabs = [
  { id: 'groups', label: 'Groups' },
  { id: 'ignored', label: 'Ignored' },
] as const
const activeTab = ref<(typeof tabs)[number]['id']>('groups')
const minLevel = ref<DuplicateLevelFilter>('check')

const percent = (value?: number | null) =>
  typeof value === 'number' ? `${Math.round(value * 100)}%` : '–'

const levelLabel = (level: string) =>
  ({ very_likely: 'Very likely', likely: 'Likely', check: 'Check' })[level] ?? level

const levelClass = (level: string) =>
  ({
    very_likely: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
    likely: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  })[level] ?? 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'

const onScan = async () => {
  const result = await startScan()
  if (!result) return
  if (!result.queued) {
    toastStore.push('Queue is disabled; scan not started.', 'warning')
    return
  }
  toastStore.push(`Duplicate scan queued for ${result.enqueued} documents.`, 'success')
}

const toggleIgnore = async (pair: DuplicatePairOut, value: boolean) => {
  if (await setIgnored(pair, value)) {
    toastStore.push(value ? 'Pair ignored.' : 'Pair restored.', 'success')
    await load(minLevel.value)
  }
}

watch(minLevel, (level) => void load(level))
onMounted(() => void load(minLevel.value))
</script>
