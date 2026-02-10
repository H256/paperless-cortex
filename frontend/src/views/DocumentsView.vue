<template>
  <section>
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight">Documents</h2>
        <p class="text-sm text-slate-500">
          Manage ingestion, embedding, and review analysis status.
        </p>
      </div>
      <div class="flex items-center gap-3">
        <div
          class="grid grid-cols-4 gap-x-3 gap-y-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          <div class="text-slate-500">Synced</div>
          <div class="font-semibold text-slate-900 dark:text-slate-100">{{ stats.total }}</div>
          <div class="text-slate-500">Queued</div>
          <div class="font-semibold text-indigo-600">
            {{ queueStatus.enabled ? (queueStatus.length ?? 0) : 0 }}
          </div>

          <div class="text-slate-500">Embeddings</div>
          <div class="font-semibold text-emerald-600">{{ stats.embeddings }}</div>
          <div class="text-slate-500">Vision OCR</div>
          <div class="font-semibold text-emerald-600">{{ stats.vision }}</div>

          <div class="text-slate-500">Suggestions</div>
          <div class="font-semibold text-emerald-600">{{ stats.suggestions }}</div>
          <div class="text-slate-500">Fully processed</div>
          <div class="font-semibold text-emerald-700 dark:text-emerald-400">
            {{ stats.fully_processed }}
          </div>

          <div class="text-slate-500">Pending</div>
          <div class="font-semibold text-amber-600">{{ stats.unprocessed }}</div>
          <div class="text-slate-500">Processed*</div>
          <div class="font-semibold text-emerald-600">{{ stats.processed }}</div>
        </div>
        <div
          v-if="isProcessing"
          class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          <Loader2 class="h-4 w-4 animate-spin text-indigo-500" />
          <div class="space-y-0.5">
            <div v-if="syncStatus.status === 'running'">
              Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) -
              ETA {{ etaText }}
            </div>
            <div v-if="embedStatus.status === 'running' || hasQueuedWork">
              {{ embedLabel }} {{ processingProcessed }} / {{ processingTotal }} ({{
                processingPercent
              }}%) - ETA {{ processingEtaText }}
            </div>
            <div
              v-if="hasQueuedWork && lastRunText !== '--'"
              class="text-xs text-slate-500 dark:text-slate-400"
            >
              Last run: {{ lastRunText }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <section
      class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex w-full flex-wrap items-center justify-end gap-3">
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          :disabled="syncing || isProcessing"
          @click="openPreview"
          title="Sync new documents and process missing intelligence items"
        >
          <RefreshCw class="h-4 w-4" />
          {{ syncing ? 'Working...' : 'Continue processing' }}
        </button>
        <button
          v-if="showCancel"
          class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
          @click="cancelProcessing"
          title="Cancel processing and clear queued jobs"
        >
          <XCircle class="h-4 w-4" />
          Cancel processing
        </button>
      </div>
    </section>

    <section
      class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Filters
      </div>
      <div class="grid gap-4 md:grid-cols-3 lg:grid-cols-8">
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Sort</label>
          <select
            v-model="ordering"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="-date">Date desc</option>
            <option value="date">Date asc</option>
            <option value="-title">Title desc</option>
            <option value="title">Title asc</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400"
            >Correspondent</label
          >
          <select
            v-model="selectedCorrespondent"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">All</option>
            <option v-for="c in correspondents" :key="c.id" :value="String(c.id)">
              {{ c.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Tag</label>
          <select
            v-model="selectedTag"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">All</option>
            <option v-for="t in tags" :key="t.id" :value="String(t.id)">
              {{ t.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">From</label>
          <input
            type="date"
            v-model="dateFrom"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">To</label>
          <input
            type="date"
            v-model="dateTo"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Analysis</label>
          <select
            v-model="analysisFilter"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="all">All</option>
            <option value="analyzed">Analyzed</option>
            <option value="not_analyzed">Not analyzed</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Model</label>
          <input
            v-model="modelFilter"
            type="text"
            placeholder="e.g. gpt-oss"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
        <div>
          <label class="text-xs font-semibold text-slate-500 dark:text-slate-400">Page size</label>
          <select
            v-model.number="pageSize"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </div>
      </div>

      <div
        class="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-600 dark:text-slate-300"
      >
        <button
          class="ml-auto inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          @click="load"
          title="Reload current list"
        >
          <RefreshCw class="h-4 w-4" />
          Reload
        </button>
      </div>
    </section>

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
                  @click.stop="toggleSort('title')"
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
                  @click.stop="toggleSort('date')"
                >
                  Date
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
              v-for="doc in visibleDocuments"
              :key="doc.id"
              class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800"
              @click="open(doc.id)"
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
                  :href="paperlessDocUrl(doc.id)"
                  target="_blank"
                  rel="noopener"
                  @click.stop
                >
                  <ExternalLink class="h-3 w-3" />
                </a>
              </td>
              <td class="px-6 py-3">
                <div
                  class="flex flex-nowrap items-center gap-1 text-xs text-slate-400 whitespace-nowrap"
                >
                  <template v-if="missingIcons(doc).length">
                    <div
                      v-for="item in missingIcons(doc)"
                      :key="item.label"
                      class="inline-flex items-center gap-1"
                      :title="`Missing ${item.label}`"
                    >
                      <component :is="item.icon" class="h-3 w-3 text-amber-500" />
                      <span class="sr-only">Missing {{ item.label }}</span>
                    </div>
                    <div
                      v-if="fulfilledCount(doc) > 0"
                      class="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-400"
                      :title="fulfilledTooltip(doc)"
                    >
                      +{{ fulfilledCount(doc) }}
                    </div>
                  </template>
                  <template v-else>
                    <div class="inline-flex items-center gap-1" title="All processed">
                      <CheckCircle class="h-3 w-3 text-emerald-500" />
                      <span class="sr-only">All processed</span>
                    </div>
                  </template>
                </div>
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
          @click="page -= 1;load()"
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
          @click="            page += 1;            load()          "
        >
          Next
        </button>
      </div>
    </section>
  </section>

  <div
    v-if="showPreviewModal"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
  >
    <div
      class="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Ready to process</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            Summary of missing intelligence tasks
          </p>
        </div>
      </div>

      <div
        v-if="syncStatus.status === 'running'"
        class="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/40 dark:text-indigo-200"
      >
        <div class="flex items-center gap-2">
          <Loader2 class="h-4 w-4 animate-spin" />
          Sync {{ syncStatus.processed }} / {{ syncStatus.total }} ({{ progressPercent }}%) - ETA
          {{ etaText }}
        </div>
        <div class="mt-1 text-[11px] text-indigo-600/80 dark:text-indigo-200/70">
          Sync is running. Start is available as soon as sync is complete.
        </div>
      </div>
      <div
        v-if="documentsStore.processPreviewLoading"
        class="mt-4 text-sm text-slate-500 dark:text-slate-400"
      >
        Calculating...
      </div>
      <div v-else class="mt-4 grid gap-3 sm:grid-cols-2">
        <div
          class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
        >
          <div class="text-xs uppercase text-slate-400">Documents</div>
          <div class="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
            {{ processPreview?.docs ?? 0 }}
          </div>
          <div class="mt-1 text-xs text-slate-500">Total checked</div>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-200"
        >
          <div class="text-xs uppercase text-slate-400">Needs work</div>
          <div class="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
            {{ processPreview?.missing_docs ?? 0 }}
          </div>
          <div class="mt-1 text-xs text-slate-500">Documents to process</div>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing vision OCR:
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_vision_ocr ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing embeddings:
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_embeddings ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing vision embeddings:
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_embeddings_vision ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing suggestions (baseline):
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_suggestions_paperless ?? 0
          }}</strong>
        </div>
        <div
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Missing suggestions (vision):
          <strong class="text-slate-900 dark:text-slate-100">{{
            processPreview?.missing_suggestions_vision ?? 0
          }}</strong>
        </div>
      </div>

      <div
        class="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div
          class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          Processing options
        </div>
        <div class="mt-3 grid gap-3 sm:grid-cols-2">
          <div
            class="flex flex-col gap-2 text-xs font-medium text-slate-700 dark:text-slate-200 sm:col-span-2"
          >
            <label for="batch-index" class="text-xs font-medium text-slate-700 dark:text-slate-200">
              Max documents to process
            </label>
            <div class="flex items-center gap-3">
              <input
                id="batch-index"
                v-model.number="batchIndex"
                type="range"
                :min="0"
                :max="batchOptions.length - 1"
                step="1"
                class="h-2 w-full cursor-pointer accent-indigo-600"
              />
              <span
                class="min-w-[3.5rem] text-right text-sm font-semibold text-slate-900 dark:text-slate-100"
              >
                {{ batchLabel }}
              </span>
            </div>
            <span class="text-[11px] text-slate-400 dark:text-slate-500">
              Use a smaller batch if your LLM server is not always online.
            </span>
          </div>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeVisionOcr"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Vision OCR
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeEmbeddings"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Embeddings
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeSuggestionsPaperless"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Suggestions (baseline)
          </label>
          <label
            class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            <input
              type="checkbox"
              v-model="processOptions.includeSuggestionsVision"
              class="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Suggestions (vision)
          </label>
          <label
            class="flex flex-col text-xs font-medium text-slate-700 dark:text-slate-200 sm:col-span-2"
          >
            Embeddings mode
            <select
              v-model="processOptions.embeddingsMode"
              :disabled="!processOptions.includeEmbeddings"
              class="mt-1 h-9 rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-900 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="auto">Auto (use vision when available)</option>
              <option value="paperless">Paperless only</option>
              <option value="vision">Vision only</option>
            </select>
          </label>
        </div>
      </div>

      <div class="mt-6 flex flex-wrap items-center justify-end gap-3">
        <button
          v-if="processStartResult"
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          @click="closePreview"
        >
          Close
        </button>
        <template v-else>
          <button
            class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            @click="closePreview"
            :disabled="processStartLoading"
          >
            Cancel
          </button>
          <button
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
            :class="{
              'cursor-not-allowed opacity-60':
                documentsStore.processPreviewLoading ||
                processStartLoading ||
                syncing ||
                isSyncingNow,
            }"
            :disabled="
              documentsStore.processPreviewLoading || processStartLoading || syncing || isSyncingNow
            "
            @click="startFromPreview"
          >
            <span v-if="processStartLoading" class="inline-flex items-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Enqueuing...
            </span>
            <span v-else-if="isSyncingNow">Syncingâ€¦</span>
            <span v-else>Start processing</span>
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch, ref, reactive, type Component } from 'vue'
import {
  CheckCircle,
  ChevronDown,
  Database,
  ExternalLink,
  Eye,
  Layers,
  Lightbulb,
  Loader2,
  Pencil,
  RefreshCw,
  ScanText,
  XCircle,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useDocumentsStore } from '../stores/documentsStore'
import { useQueueStore } from '../stores/queueStore'
import { useToastStore } from '../stores/toastStore'
import { useStatusStore } from '../stores/statusStore'
import type {DocumentRow} from '../services/documents'

const router = useRouter()
const documentsStore = useDocumentsStore()
const queueStore = useQueueStore()
const statusStore = useStatusStore()
const toastStore = useToastStore()

const {
  documents,
  page,
  pageSize,
  ordering,
  totalCount,
  tags,
  correspondents,
  selectedTag,
  selectedCorrespondent,
  dateFrom,
  dateTo,
  syncing,
  lastSynced,
  syncStatus,
  embedStatus,
  stats,
  processPreview,
  processStartLoading,
  processStartResult,
} = storeToRefs(documentsStore)

const { status: queueStatus } = storeToRefs(queueStore)

const showPreviewModal = computed(() => processPreview.value !== null)
const analysisFilter = ref<'all' | 'analyzed' | 'not_analyzed'>('all')
const modelFilter = ref('')
const processOptions = reactive({
  includeVisionOcr: true,
  includeEmbeddings: true,
  includeSuggestionsPaperless: true,
  includeSuggestionsVision: true,
  embeddingsMode: 'auto' as 'auto' | 'paperless' | 'vision',
})
const batchOptions = [10, 20, 50, 100, 200, 500, 'All'] as const
const batchIndex = ref(batchOptions.length - 1)
const batchLimit = computed(() => {
  const value = batchOptions[batchIndex.value]
  return value === 'All' ? null : value
})
const batchLabel = computed(() => (batchLimit.value === null ? 'All' : String(batchLimit.value)))

const processParams = () => ({
  include_vision_ocr: processOptions.includeVisionOcr,
  include_embeddings: processOptions.includeEmbeddings,
  include_suggestions_paperless: processOptions.includeSuggestionsPaperless,
  include_suggestions_vision: processOptions.includeSuggestionsVision,
  embeddings_mode: processOptions.embeddingsMode,
  limit: batchLimit.value ?? undefined,
})

const paperlessBaseUrl = computed(
  () => import.meta.env.VITE_PAPERLESS_BASE_URL || statusStore.paperlessBaseUrl || '',
)
const paperlessDocUrl = (id: number) =>
  paperlessBaseUrl.value ? `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${id}` : ''

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const isProcessing = computed(
  () => syncStatus.value.status === 'running' || embedStatus.value.status === 'running',
)
const isSyncingNow = computed(() => syncStatus.value.status === 'running')
const hasQueuedWork = computed(() => {
  if (!queueStatus.value.enabled) return false
  return (queueStatus.value.length ?? 0) > 0 || (queueStatus.value.in_progress ?? 0) > 0
})
const showCancel = computed(() => isProcessing.value || hasQueuedWork.value)
const embedLabel = computed(() => {
  if (queueStore.status.enabled && (queueStore.status.length || queueStore.status.in_progress)) {
    return 'Queue'
  }
  return 'Embed'
})
const sortDir = (field: string) => {
  const current = ordering.value.replace('-', '')
  if (current !== field) return null
  return ordering.value.startsWith('-') ? 'desc' : 'asc'
}

const toggleSort = (field: string) => {
  const dir = sortDir(field)
  if (!dir || dir === 'desc') {
    ordering.value = field
  } else {
    ordering.value = `-${field}`
  }
  page.value = 1
}
const progressPercent = computed(() => {
  if (!syncStatus.value.total) return 0
  return Math.min(100, Math.round((syncStatus.value.processed / syncStatus.value.total) * 100))
})
const etaText = computed(() => {
  if (syncStatus.value.eta_seconds !== null && syncStatus.value.eta_seconds !== undefined) {
    const minutes = Math.floor(syncStatus.value.eta_seconds / 60)
    const seconds = syncStatus.value.eta_seconds % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }
  if (!syncStatus.value.started_at || !syncStatus.value.processed) return '--'
  const started = Date.parse(syncStatus.value.started_at)
  if (Number.isNaN(started)) return '--'
  const elapsedMs = Date.now() - started
  const rate = syncStatus.value.processed / Math.max(1, elapsedMs / 1000)
  if (!syncStatus.value.total || rate <= 0) return '--'
  const remaining = syncStatus.value.total - syncStatus.value.processed
  const etaSec = Math.max(0, Math.round(remaining / rate))
  const minutes = Math.floor(etaSec / 60)
  const seconds = etaSec % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})
const formatDuration = (totalSeconds: number) => {
  const safe = Math.max(0, Math.round(totalSeconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const seconds = safe % 60
  return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

const queueOutstanding = computed(
  () => (queueStatus.value.length ?? 0) + (queueStatus.value.in_progress ?? 0),
)
const queueIsIdle = computed(() => !queueStatus.value.enabled || queueOutstanding.value === 0)
const queueProcessed = computed(() => (queueIsIdle.value ? 0 : (queueStatus.value.done ?? 0)))
const queueTotal = computed(() =>
  queueIsIdle.value
    ? 0
    : Math.max(queueStatus.value.total ?? 0, queueProcessed.value + queueOutstanding.value),
)
const queueEtaText = computed(() => {
  const lastRun = queueStatus.value.last_run_seconds ?? null
  if (!lastRun || !queueOutstanding.value) return '--'
  return formatDuration(lastRun * queueOutstanding.value)
})
const lastRunText = computed(() => {
  const lastRun = queueStatus.value.last_run_seconds ?? null
  if (!lastRun) return '--'
  return formatDuration(lastRun)
})

const processingProcessed = computed(() =>
  hasQueuedWork.value ? queueProcessed.value : embedStatus.value.processed,
)
const processingTotal = computed(() =>
  hasQueuedWork.value ? queueTotal.value : embedStatus.value.total,
)
const processingPercent = computed(() => {
  if (!processingTotal.value) return 0
  return Math.min(100, Math.round((processingProcessed.value / processingTotal.value) * 100))
})
const processingEtaText = computed(() => {
  if (hasQueuedWork.value) return queueEtaText.value
  if (embedStatus.value.eta_seconds !== null && embedStatus.value.eta_seconds !== undefined) {
    const minutes = Math.floor(embedStatus.value.eta_seconds / 60)
    const seconds = embedStatus.value.eta_seconds % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }
  if (!embedStatus.value.started_at || !embedStatus.value.processed) return '--'
  const started = Date.parse(embedStatus.value.started_at)
  if (Number.isNaN(started)) return '--'
  const elapsedMs = Date.now() - started
  const rate = embedStatus.value.processed / Math.max(1, elapsedMs / 1000)
  if (!embedStatus.value.total || rate <= 0) return '--'
  const remaining = embedStatus.value.total - embedStatus.value.processed
  return formatDuration(remaining / rate)
})

const load = async () => {
  try {
    await documentsStore.load()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load documents'
    toastStore.push(message, 'danger', 'Error')
  }
}

const openPreview = async () => {
  await documentsStore.continueProcessingPreview(processParams())
}

const closePreview = () => {
  documentsStore.clearProcessPreview()
}

const startFromPreview = async () => {
  await documentsStore.startProcessingFromPreview(processParams())
  if (processStartResult.value) {
    toastStore.push(
      `Enqueued ${processStartResult.value.enqueued ?? 0} docs (${processStartResult.value.tasks ?? 0} tasks).`,
      'success',
      'Queue started',
    )
  }
  documentsStore.clearProcessPreview()
}

const cancelProcessing = async () => {
  await documentsStore.cancelProcessing()
  await queueStore.clear()
  await load()
}

const open = (id: number) => {
  router.push(`/documents/${id}`)
}

const correspondentLabel = (id?: number | null, name?: string | null) => {
  if (name) return name
  if (!id) return ''
  return correspondents.value.find((c) => c.id === id)?.name ?? String(id)
}

const hasDerived = (doc: DocumentRow) => {
  return Boolean(doc.has_embeddings || doc.has_suggestions || doc.has_vision_pages)
}

const missingIcons = (doc: DocumentRow) => {
  const items: { label: string; icon: Component }[] = []
  if (!doc.has_embeddings) items.push({ label: 'Embeddings', icon: Layers })
  if (!doc.has_vision_pages) items.push({ label: 'Vision OCR', icon: ScanText })
  if (!doc.has_suggestions_paperless)
    items.push({ label: 'Suggestions (paperless)', icon: Lightbulb })
  if (doc.has_vision_pages && !doc.has_suggestions_vision)
    items.push({ label: 'Suggestions (vision)', icon: Eye })
  if (!doc.local_cached) items.push({ label: 'Local cache', icon: RefreshCw })
  const order = new Map<string, number>([
    ['Embeddings', 1],
    ['Vision OCR', 2],
    ['Suggestions (paperless)', 3],
    ['Suggestions (vision)', 4],
    ['Local cache', 5],
  ])
  return items.sort((a, b) => (order.get(a.label) ?? 99) - (order.get(b.label) ?? 99))
}

const fulfilledTooltip = (doc: DocumentRow) => {
  const done: string[] = []
  if (doc.has_embeddings) done.push('Embeddings')
  if (doc.has_vision_pages) done.push('Vision OCR')
  if (doc.has_suggestions_paperless) done.push('Suggestions (paperless)')
  if (doc.has_vision_pages && doc.has_suggestions_vision) done.push('Suggestions (vision)')
  if (doc.local_cached) done.push('Local cache')
  if (!done.length) return 'Nothing processed yet'
  return `Done: ${done.join(', ')}`
}

const fulfilledCount = (doc: DocumentRow) => {
  let count = 0
  if (doc.has_embeddings) count += 1
  if (doc.has_vision_pages) count += 1
  if (doc.has_suggestions_paperless) count += 1
  if (doc.has_vision_pages && doc.has_suggestions_vision) count += 1
  if (doc.local_cached) count += 1
  return count
}

const visibleDocuments = computed(() => {
  let filtered = documents.value
  if (analysisFilter.value !== 'all') {
    const shouldBeAnalyzed = analysisFilter.value === 'analyzed'
    filtered = filtered.filter((doc) => hasDerived(doc) === shouldBeAnalyzed)
  }
  const needle = modelFilter.value.trim().toLowerCase()
  if (!needle) return filtered
  return filtered.filter((doc) =>
    String(doc.analysis_model || '')
      .toLowerCase()
      .includes(needle),
  )
})

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

onMounted(async () => {
  await documentsStore.fetchMeta()
  await load()
})

watch(
  () => ({ ...processOptions }),
  async () => {
    if (!showPreviewModal.value) return
    await documentsStore.refreshProcessPreview(processParams())
  },
  { deep: true },
)

watch(batchIndex, async () => {
  if (!showPreviewModal.value) return
  await documentsStore.refreshProcessPreview(processParams())
})

watch(ordering, async () => {
  await load()
})
</script>

