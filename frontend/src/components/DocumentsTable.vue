<template>
  <section
    class="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div v-if="viewMode === 'cards'" class="space-y-3 p-3 sm:p-4">
      <button
        v-for="doc in documents"
        :key="doc.id ?? `${doc.title}-${doc.created ?? ''}`"
        class="block w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-left hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600"
        @click="onOpenDoc(doc.id)"
      >
        <div class="text-sm font-semibold text-slate-900 dark:text-slate-100">
          {{ doc.title || `Document ${doc.id ?? '-'}` }}
        </div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {{ formatDate(doc.document_date || doc.created) || '-' }}
          <span v-if="correspondentLabel(doc.correspondent, doc.correspondent_name)">
            | {{ correspondentLabel(doc.correspondent, doc.correspondent_name) }}
          </span>
        </div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <div
            class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-900"
            :title="doc.local_cached ? 'Paperless + local cache' : 'Paperless only'"
          >
            <Database
              class="h-3.5 w-3.5"
              :class="doc.local_cached ? 'text-indigo-600' : 'text-slate-400'"
            />
            <span class="text-slate-500 dark:text-slate-400">{{ doc.local_cached ? 'Cached' : 'Paperless' }}</span>
          </div>
          <a
            v-if="paperlessBaseUrl"
            class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :href="paperlessDocUrl(doc.id ?? 0)"
            target="_blank"
            rel="noopener"
            @click.stop
          >
            <ExternalLink class="h-3 w-3" />
            Paperless
          </a>
          <div
            v-if="doc.local_overrides"
            class="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs dark:border-amber-900/50 dark:bg-amber-950/40"
            title="Local values override Paperless"
          >
            <Pencil class="h-3.5 w-3.5 text-amber-600" />
            <span class="text-amber-700 dark:text-amber-300">Overrides</span>
          </div>
        </div>
        <div class="mt-2 space-y-1">
          <DocumentProcessingBadges :doc="doc" />
          <div
            v-if="doc.id != null && runningByDocId[doc.id]"
            class="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
            :title="runningByDocId[doc.id]"
          >
            {{ runningByDocId[doc.id] }}
          </div>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            @click.stop="copyDocId(doc.id)"
          >
            {{ copiedDocId === doc.id ? 'Copied' : 'Copy ID' }}
          </button>
          <button
            type="button"
            class="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            @click.stop="onOpenDoc(doc.id)"
          >
            Open
          </button>
          <button
            type="button"
            class="rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
            @click.stop="onOpenDocOperations(doc.id)"
          >
            Continue
          </button>
          <button
            v-if="needsReview(doc)"
            type="button"
            class="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 hover:border-amber-300 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
            @click.stop="onOpenDocSuggestions(doc.id)"
          >
            Review
          </button>
        </div>
      </button>
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full min-w-[720px] border-collapse text-sm lg:min-w-[920px]">
        <thead
          class="sticky top-0 z-10 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400"
        >
          <tr>
            <th class="px-6 py-3">
              <button
                class="inline-flex items-center gap-1"
                type="button"
                @click.stop="$emit('toggle-sort', 'title')"
              >
                Title
                <ChevronDown
                  v-if="sortDir('title')"
                  class="h-3 w-3 text-slate-400"
                  :class="{ 'rotate-180': sortDir('title') === 'desc' }"
                />
              </button>
            </th>
            <th class="px-6 py-3">
              <button
                class="inline-flex items-center gap-1"
                type="button"
                @click.stop="$emit('toggle-sort', 'date')"
              >
                Issue date
                <ChevronDown
                  v-if="sortDir('date')"
                  class="h-3 w-3 text-slate-400"
                  :class="{ 'rotate-180': sortDir('date') === 'desc' }"
                />
              </button>
            </th>
            <th class="px-6 py-3">Correspondent</th>
            <th class="hidden px-6 py-3 lg:table-cell">Source</th>
            <th class="hidden px-6 py-3 xl:table-cell">Links</th>
            <th class="px-6 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="doc in documents"
            :key="doc.id ?? `${doc.title}-${doc.created ?? ''}`"
            class="border-b border-slate-100 hover:bg-slate-50 focus-within:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800 dark:focus-within:bg-slate-800"
            tabindex="0"
            role="button"
            :aria-label="`Open document ${doc.title || doc.id || ''}`"
            @click="onOpenDoc(doc.id)"
            @keydown.enter.prevent="onOpenDoc(doc.id)"
            @keydown.space.prevent="onOpenDoc(doc.id)"
          >
            <td class="px-6 py-3 text-slate-900 dark:text-slate-100">{{ doc.title }}</td>
            <td class="px-6 py-3 text-slate-600">
              {{ formatDate(doc.document_date || doc.created) }}
            </td>
            <td class="px-6 py-3 text-slate-600">
              {{ correspondentLabel(doc.correspondent, doc.correspondent_name) }}
            </td>
            <td class="hidden px-6 py-3 lg:table-cell">
              <div class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <div
                  class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
                  :title="doc.local_cached ? 'Paperless + local cache' : 'Paperless only'"
                >
                  <Database
                    class="h-3.5 w-3.5"
                    :class="doc.local_cached ? 'text-indigo-600' : 'text-slate-400'"
                  />
                </div>
                <div
                  v-if="doc.local_overrides"
                  class="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-1 dark:border-amber-900/50 dark:bg-amber-950/40"
                  title="Local values override Paperless"
                >
                  <Pencil class="h-3.5 w-3.5 text-amber-600" />
                </div>
              </div>
            </td>
            <td class="hidden px-6 py-3 text-slate-600 xl:table-cell">
              <a
                v-if="paperlessBaseUrl"
                class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
                :href="paperlessDocUrl(doc.id ?? 0)"
                target="_blank"
                rel="noopener"
                @click.stop
              >
                <ExternalLink class="h-3 w-3" />
              </a>
            </td>
            <td class="px-6 py-3">
              <div class="space-y-1">
                <DocumentProcessingBadges :doc="doc" />
                <div
                  v-if="doc.id != null && runningByDocId[doc.id]"
                  class="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
                  :title="runningByDocId[doc.id]"
                >
                  {{ runningByDocId[doc.id] }}
                </div>
                <div class="flex flex-wrap items-center gap-1.5 pt-1">
                  <button
                    type="button"
                    class="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                    @click.stop="copyDocId(doc.id)"
                  >
                    {{ copiedDocId === doc.id ? 'Copied' : 'Copy ID' }}
                  </button>
                  <button
                    type="button"
                    class="hidden rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-semibold text-slate-600 hover:border-slate-300 md:inline-flex dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                    @click.stop="onOpenDoc(doc.id)"
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    class="rounded border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[11px] font-semibold text-indigo-700 hover:border-indigo-300 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
                    @click.stop="onOpenDocOperations(doc.id)"
                  >
                    Continue
                  </button>
                  <button
                    v-if="needsReview(doc)"
                    type="button"
                    class="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[11px] font-semibold text-amber-700 hover:border-amber-300 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
                    @click.stop="onOpenDocSuggestions(doc.id)"
                  >
                    Review
                  </button>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      class="flex flex-col gap-3 px-4 py-4 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-6 dark:text-slate-300"
    >
      <button
        class="w-full rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm sm:w-auto dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        :disabled="page <= 1"
        @click="$emit('prev-page')"
      >
        Prev
      </button>
      <div class="text-center sm:text-center">
        <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Page {{ page }} of {{ totalPages }}
        </div>
        <div class="text-xs text-slate-400 dark:text-slate-500">
          Last synced: {{ formatDateTime(lastSynced) }}
        </div>
        <div class="mt-2 flex items-center justify-center gap-1">
          <input
            v-model.number="pageJumpValue"
            type="number"
            min="1"
            :max="totalPages"
            class="w-20 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            @keyup.enter="applyPageJump"
          />
          <button
            type="button"
            class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            @click="applyPageJump"
          >
            Go
          </button>
        </div>
      </div>
      <button
        class="w-full rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm sm:w-auto dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        :disabled="page >= totalPages"
        @click="$emit('next-page')"
      >
        Next
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ChevronDown, Database, ExternalLink, Pencil } from 'lucide-vue-next'
import DocumentProcessingBadges from './DocumentProcessingBadges.vue'
import type { Correspondent, DocumentRow } from '../services/documents'

const props = defineProps<{
  documents: DocumentRow[]
  runningByDocId: Record<number, string>
  ordering: string
  viewMode: 'table' | 'cards'
  correspondents: Correspondent[]
  paperlessBaseUrl: string
  page: number
  totalPages: number
  lastSynced: string | null
}>()

const emit = defineEmits<{
  'toggle-sort': [field: string]
  'open-doc': [id: number]
  'open-doc-operations': [id: number]
  'open-doc-suggestions': [id: number]
  'prev-page': []
  'next-page': []
  'jump-page': [page: number]
}>()

const pageJumpValue = ref<number>(props.page)
const copiedDocId = ref<number | null>(null)

watch(
  () => props.page,
  (value) => {
    pageJumpValue.value = value
  },
)

const applyPageJump = () => {
  const next = Number(pageJumpValue.value)
  if (!Number.isFinite(next)) return
  const clamped = Math.min(Math.max(1, Math.trunc(next)), props.totalPages)
  if (clamped === props.page) return
  pageJumpValue.value = clamped
  emit('jump-page', clamped)
}

const sortDir = (field: string) => {
  const current = props.ordering.replace('-', '')
  if (current !== field) return null
  return props.ordering.startsWith('-') ? 'desc' : 'asc'
}

const onOpenDoc = (id: number | null | undefined) => {
  if (typeof id !== 'number') return
  emit('open-doc', id)
}

const onOpenDocOperations = (id: number | null | undefined) => {
  if (typeof id !== 'number') return
  emit('open-doc-operations', id)
}

const onOpenDocSuggestions = (id: number | null | undefined) => {
  if (typeof id !== 'number') return
  emit('open-doc-suggestions', id)
}

const copyDocId = async (id: number | null | undefined) => {
  if (typeof id !== 'number') return
  try {
    await navigator.clipboard.writeText(String(id))
    copiedDocId.value = id
    window.setTimeout(() => {
      if (copiedDocId.value === id) copiedDocId.value = null
    }, 1200)
  } catch {
    // no-op fallback; clipboard may be unavailable in some contexts
  }
}

const needsReview = (doc: DocumentRow) =>
  doc.review_status === 'needs_review' || Boolean(doc.local_overrides)

const correspondentLabel = (id?: number | null, name?: string | null) => {
  if (name) return name
  if (!id) return ''
  return props.correspondents.find((c) => c.id === id)?.name ?? String(id)
}

const paperlessDocUrl = (id: number) =>
  props.paperlessBaseUrl ? `${props.paperlessBaseUrl.replace(/\/$/, '')}/documents/${id}` : ''

const formatDate = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language).format(parsed)
}

const formatDateTime = (value?: string | null) => {
  if (!value) return 'never'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}
</script>
