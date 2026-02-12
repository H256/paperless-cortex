<template>
  <section
    class="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div>
      <table class="w-full border-collapse text-sm">
        <thead
          class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400"
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
            <th class="px-6 py-3">Source</th>
            <th class="px-6 py-3">Links</th>
            <th class="px-6 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="doc in documents"
            :key="doc.id ?? `${doc.title}-${doc.created ?? ''}`"
            class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800"
            @click="onOpenDoc(doc.id)"
          >
            <td class="px-6 py-3 text-slate-900 dark:text-slate-100">{{ doc.title }}</td>
            <td class="px-6 py-3 text-slate-600">
              {{ formatDate(doc.document_date || doc.created) }}
            </td>
            <td class="px-6 py-3 text-slate-600">
              {{ correspondentLabel(doc.correspondent, doc.correspondent_name) }}
            </td>
            <td class="px-6 py-3">
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
            <td class="px-6 py-3 text-slate-600">
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
              <DocumentProcessingBadges :doc="doc" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      class="flex items-center justify-between px-6 py-4 text-sm text-slate-600 dark:text-slate-300"
    >
      <button
        class="rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        :disabled="page <= 1"
        @click="$emit('prev-page')"
      >
        Prev
      </button>
      <div class="text-center">
        <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Page {{ page }} of {{ totalPages }}
        </div>
        <div class="text-xs text-slate-400 dark:text-slate-500">
          Last synced: {{ formatDateTime(lastSynced) }}
        </div>
      </div>
      <button
        class="rounded-lg border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        :disabled="page >= totalPages"
        @click="$emit('next-page')"
      >
        Next
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ChevronDown, Database, ExternalLink, Pencil } from 'lucide-vue-next'
import DocumentProcessingBadges from './DocumentProcessingBadges.vue'
import type { Correspondent, DocumentRow } from '../services/documents'

const props = defineProps<{
  documents: DocumentRow[]
  ordering: string
  correspondents: Correspondent[]
  paperlessBaseUrl: string
  page: number
  totalPages: number
  lastSynced: string | null
}>()

const emit = defineEmits<{
  'toggle-sort': [field: string]
  'open-doc': [id: number]
  'prev-page': []
  'next-page': []
}>()

const sortDir = (field: string) => {
  const current = props.ordering.replace('-', '')
  if (current !== field) return null
  return props.ordering.startsWith('-') ? 'desc' : 'asc'
}

const onOpenDoc = (id: number | null | undefined) => {
  if (typeof id !== 'number') return
  emit('open-doc', id)
}

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
