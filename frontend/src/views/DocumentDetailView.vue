<template>
  <section>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          {{ document?.title || `Document ${id}` }}
        </h2>
        <p class="text-sm text-slate-500 dark:text-slate-400">{{ headerMetaLine }}</p>
        <p
          v-if="activeRunLabel"
          class="mt-1 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
        >
          Processing now: {{ activeRunLabel }}
        </p>
      </div>
      <div class="flex w-full flex-wrap items-center gap-2 md:w-auto md:justify-end">
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:border-slate-300 sm:text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          @click="navigateBackToDocuments"
        >
          <ArrowLeft class="h-4 w-4" />
          Back
        </button>
        <IconButton
          v-if="paperlessUrl"
          :href="paperlessUrl"
          title="Open document in Paperless"
          aria-label="Open document in Paperless"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <IconButton
          v-else
          disabled
          title="Set VITE_PAPERLESS_BASE_URL to enable link"
          aria-label="Paperless link unavailable"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 shadow-sm hover:border-emerald-300 sm:text-sm dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200"
          :disabled="reviewMarking || !canMarkReviewed"
          :class="reviewMarking || !canMarkReviewed ? 'cursor-not-allowed opacity-70' : ''"
          title="Marks this document as reviewed without applying suggestions."
          @click="markReviewedAction"
        >
          <CheckCircle class="h-4 w-4" :class="reviewMarking ? 'animate-pulse' : ''" />
          {{ reviewMarking ? 'Marking...' : 'Mark reviewed' }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-semibold text-indigo-700 shadow-sm hover:border-indigo-300 sm:text-sm dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
          :disabled="writebackRunning || !canWriteback"
          :class="writebackRunning || !canWriteback ? 'cursor-not-allowed opacity-70' : ''"
          :title="writebackButtonTitle"
          @click="openWritebackConfirm"
        >
          <ClipboardCheck class="h-4 w-4" :class="writebackRunning ? 'animate-pulse' : ''" />
          {{ writebackButtonLabel }}
        </button>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 sm:text-sm"
          :disabled="reloadingAll"
          :class="reloadingAll ? 'cursor-not-allowed opacity-70' : ''"
          @click="reloadAll"
        >
          <RefreshCw class="h-4 w-4" :class="reloadingAll ? 'animate-spin' : ''" />
          {{ reloadingAll ? 'Reloading...' : 'Reload' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="mt-6 text-sm text-slate-500">Loading...</div>
    <div v-else class="mt-6 space-y-4">
      <div class="rounded-xl border border-slate-200 bg-white p-2 text-xs font-semibold text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
        <div class="overflow-x-auto">
          <div class="flex min-w-max items-center gap-2">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="rounded-lg px-3 py-1.5"
              :class="
                activeTab === tab.key
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
              "
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>
      </div>

      <DocumentMetadataSection v-if="activeTab === 'meta'" :rows="rows" />

      <DocumentTextQualitySection
        v-if="activeTab === 'text'"
        :content="document?.content || ''"
        :content-quality="contentQuality"
        :content-quality-error="contentQualityError"
        :ocr-scores="ocrScores"
        :ocr-scores-loading="ocrScoresLoading"
        :ocr-scores-error="ocrScoresError"
      />

      <DocumentSuggestionsSection
        v-if="activeTab === 'suggestions'"
        :suggestions="suggestions"
        :suggestions-error="suggestionsError"
        :suggestions-loading="suggestionsLoading"
        :suggestion-variants="suggestionVariants"
        :suggestion-variant-loading="suggestionVariantLoading"
        :suggestion-variant-error="suggestionVariantError"
        :current-values="currentValues"
        @refresh="refreshSuggestionsAction"
        @suggest-field="suggestFieldAction"
        @apply-variant="applyVariantOnly"
        @apply-variant-to-document="applyVariantToDocument"
        @apply-to-document="applyToDocument"
      />

      <DocumentPagesSection
        v-if="activeTab === 'pages'"
        :page-texts="pageTexts"
        :vision-progress="pageTextsVisionProgress"
        :page-texts-error="pageTextsError"
        :aggregated-text="aggregatedText"
        :pdf-page="pdfPage"
        @jump-to-page="onPdfPageChange"
      />

      <section
        v-if="activeTab === 'operations'"
        class="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Document operations</h3>
            <p class="text-xs text-slate-500 dark:text-slate-400">
              Trigger single processing steps or fully reset and rebuild this document.
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button
              class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              :disabled="docOpsLoading || pipelineStatusLoading || continuePipelineLoading"
              title="Checks missing processing steps for this document and enqueues only those tasks."
              @click="runContinuePipeline"
            >
              {{ continuePipelineLoading ? 'Checking + enqueueing...' : 'Continue missing processing' }}
            </button>
            <button
              class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              @click="router.push('/queue')"
            >
              Queue
            </button>
            <button
              class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              @click="router.push('/logs')"
            >
              Logs
            </button>
          </div>
        </div>
        <div
          v-if="continuePipelineLoading || continueQueuedWaiting"
          class="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200"
        >
          <span v-if="continuePipelineLoading">Checking missing steps and enqueueing tasks...</span>
          <span v-else-if="continueQueuedWaiting && !hasActiveTaskRuns">
            Tasks enqueued. Waiting for worker pickup...
          </span>
          <span v-else>
            Worker picked up tasks. Progress is visible in timeline and fan-out below.
          </span>
        </div>

        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
              Processing status
            </div>
            <div class="text-xs text-slate-500 dark:text-slate-300">
              Done {{ processingDoneCount }} / {{ processingRequiredCount }} required
            </div>
          </div>
          <div class="mt-1 text-xs text-slate-500 dark:text-slate-300">
            Preferred source: {{ toTitle(pipelinePreferredSource) }}
          </div>
          <div class="mt-1 text-xs" :class="isLargeDocumentMode ? 'text-indigo-600 dark:text-indigo-300' : 'text-slate-500 dark:text-slate-300'">
            {{ largeDocumentHint }}
          </div>
          <div v-if="pipelineStatusLoading" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
            Loading pipeline status...
          </div>
          <div v-else-if="pipelineStatusError" class="mt-2 text-xs text-rose-600 dark:text-rose-300">
            {{ pipelineStatusError }}
          </div>
          <div v-else-if="!processingStatusItems.length" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
            No processing status available.
          </div>
          <div class="mt-2 grid gap-2 md:grid-cols-2">
            <div
              v-for="item in processingStatusItems"
              :key="item.label"
              class="flex items-center justify-between rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900"
            >
              <span class="text-slate-700 dark:text-slate-200">{{ item.label }}</span>
              <span
                class="inline-flex items-center gap-1 font-semibold"
                :class="processingBadgeClass(item.state)"
                :title="item.detail"
              >
                <CheckCircle v-if="item.state === 'done'" class="h-3.5 w-3.5" />
                <AlertTriangle v-else-if="item.state === 'missing'" class="h-3.5 w-3.5" />
                <MinusCircle v-else class="h-3.5 w-3.5" />
                {{ processingStateLabel(item.state) }}
              </span>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
              Downstream fan-out
            </div>
            <button
              class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              :disabled="pipelineFanoutLoading"
              @click="reloadPipelineFanout"
            >
              {{ pipelineFanoutLoading ? 'Loading...' : 'Reload fan-out' }}
            </button>
          </div>
          <div v-if="pipelineFanoutError" class="mt-2 text-xs text-rose-600 dark:text-rose-300">
            {{ pipelineFanoutError }}
          </div>
          <div v-else-if="!pipelineFanoutItems.length" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
            No downstream fan-out tasks available.
          </div>
          <template v-else>
            <div class="mt-2 space-y-2 md:hidden">
              <article
                v-for="item in pipelineFanoutItems"
                :key="`fanout-mobile-${item.order}-${item.task}-${item.source || ''}`"
                class="rounded-md border border-slate-200 bg-white p-2 text-xs dark:border-slate-700 dark:bg-slate-900"
              >
                <div class="flex items-center justify-between gap-2">
                  <div class="font-semibold">{{ item.order }}. {{ item.task }}</div>
                  <div class="font-semibold" :class="fanoutStatusClass(item.status)">{{ item.status }}</div>
                </div>
                <div v-if="item.source" class="mt-1 text-slate-500 dark:text-slate-400">Source: {{ item.source }}</div>
                <div class="mt-1 text-slate-500 dark:text-slate-400">
                  Last run: {{ toRelativeTime(item.last_started_at) }}
                  <span v-if="item.checkpoint" class="ml-1">· {{ checkpointLabel(item.checkpoint as Record<string, unknown>) }}</span>
                </div>
                <div class="mt-1 text-rose-600 dark:text-rose-300">Error: {{ item.error_type || '-' }}</div>
              </article>
            </div>
            <div class="mt-2 hidden overflow-x-auto md:block">
              <table class="min-w-full text-xs">
              <thead class="text-left text-slate-500 dark:text-slate-400">
                <tr>
                  <th class="px-2 py-1">#</th>
                  <th class="px-2 py-1">Task</th>
                  <th class="px-2 py-1">Status</th>
                  <th class="px-2 py-1">Last run</th>
                  <th class="px-2 py-1">Error</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in pipelineFanoutItems" :key="`${item.order}-${item.task}-${item.source || ''}`" class="border-t border-slate-100 dark:border-slate-700">
                  <td class="px-2 py-1.5">{{ item.order }}</td>
                  <td class="px-2 py-1.5">{{ item.task }}<span v-if="item.source" class="text-slate-400"> ({{ item.source }})</span></td>
                  <td class="px-2 py-1.5" :class="fanoutStatusClass(item.status)">{{ item.status }}</td>
                  <td class="px-2 py-1.5" :title="toDateTime(item.last_started_at)">
                    {{ toRelativeTime(item.last_started_at) }}
                    <span v-if="item.checkpoint" class="ml-1 text-slate-400">· {{ checkpointLabel(item.checkpoint as Record<string, unknown>) }}</span>
                  </td>
                  <td class="px-2 py-1.5">{{ item.error_type || '-' }}</td>
                </tr>
              </tbody>
              </table>
            </div>
          </template>
        </div>

        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
              Processing timeline
            </div>
            <div class="flex w-full flex-wrap items-end gap-2 sm:w-auto sm:justify-end">
              <label class="flex flex-col text-[11px] font-medium text-slate-500 dark:text-slate-300">
                Status
                <select
                  v-model="timelineStatusFilter"
                  class="mt-1 h-8 w-24 rounded-md border border-slate-200 bg-white px-1.5 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="">all</option>
                  <option value="running">running</option>
                  <option value="retrying">retrying</option>
                  <option value="failed">failed</option>
                  <option value="done">done</option>
                </select>
              </label>
              <label class="flex flex-col text-[11px] font-medium text-slate-500 dark:text-slate-300">
                Search
                <input
                  v-model="timelineQueryFilter"
                  type="text"
                  placeholder="task/error..."
                  class="mt-1 h-8 w-40 rounded-md border border-slate-200 bg-white px-1.5 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>
              <button
                class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                :disabled="taskRunsLoading"
                @click="refreshTaskRuns"
              >
                {{ taskRunsLoading ? 'Loading...' : 'Reload timeline' }}
              </button>
            </div>
          </div>
          <div v-if="taskRunsError" class="mt-2 text-xs text-rose-600 dark:text-rose-300">
            {{ taskRunsError }}
          </div>
          <div v-else-if="!taskRuns.length" class="mt-2 text-xs text-slate-500 dark:text-slate-300">
            No task runs for this document yet.
          </div>
          <template v-else>
            <div class="mt-2 space-y-2 md:hidden">
              <article
                v-for="run in taskRuns"
                :key="`taskrun-mobile-${run.id}`"
                class="rounded-md border border-slate-200 bg-white p-2 text-xs dark:border-slate-700 dark:bg-slate-900"
              >
                <div class="flex items-center justify-between gap-2">
                  <div class="font-semibold">{{ run.task }}</div>
                  <div
                    class="font-semibold"
                    :class="run.status === 'failed' ? 'text-rose-700 dark:text-rose-300' : 'text-slate-700 dark:text-slate-200'"
                  >
                    {{ run.status }}
                  </div>
                </div>
                <div class="mt-1 text-slate-500 dark:text-slate-400">
                  Started: {{ toRelativeTime(run.started_at) }} · Attempt {{ run.attempt ?? 1 }}
                </div>
                <div class="mt-1 text-slate-500 dark:text-slate-400">
                  Checkpoint: {{ checkpointLabel(run.checkpoint) }}
                </div>
                <div v-if="embeddingTelemetryLabel(run.checkpoint)" class="mt-1 text-[11px] text-amber-600 dark:text-amber-300">
                  {{ embeddingTelemetryLabel(run.checkpoint) }}
                </div>
                <div class="mt-1 text-rose-600 dark:text-rose-300">
                  {{ run.error_type || '-' }}
                </div>
                <div v-if="run.error_message" class="mt-1 text-[11px] text-slate-500 dark:text-slate-400" :title="run.error_message">
                  {{ compactErrorMessage(run.error_message) }}
                </div>
                <div class="mt-2 flex flex-wrap items-center gap-1.5">
                  <button
                    v-if="run.status === 'failed'"
                    class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                    :disabled="docOpsLoading"
                    @click="retryTaskRun(run)"
                  >
                    Retry
                  </button>
                  <button
                    v-if="run.error_message"
                    class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                    :disabled="docOpsLoading"
                    @click="copyRunError(run.error_message)"
                  >
                    Copy error
                  </button>
                </div>
              </article>
            </div>
            <div class="mt-2 hidden overflow-x-auto md:block">
              <table class="min-w-full text-xs">
              <thead class="text-left text-slate-500 dark:text-slate-400">
                <tr>
                  <th class="px-2 py-1">Started</th>
                  <th class="px-2 py-1">Task</th>
                  <th class="px-2 py-1">Status</th>
                  <th class="px-2 py-1">Attempt</th>
                  <th class="px-2 py-1">Checkpoint</th>
                  <th class="px-2 py-1">Error</th>
                  <th class="px-2 py-1">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="run in taskRuns" :key="run.id" class="border-t border-slate-100 dark:border-slate-700">
                  <td class="px-2 py-1.5" :title="toDateTime(run.started_at)">{{ toRelativeTime(run.started_at) }}</td>
                  <td class="px-2 py-1.5">{{ run.task }}</td>
                  <td class="px-2 py-1.5" :class="run.status === 'failed' ? 'text-rose-700 dark:text-rose-300 font-semibold' : 'text-slate-700 dark:text-slate-200'">
                    {{ run.status }}
                  </td>
                  <td class="px-2 py-1.5">{{ run.attempt ?? 1 }}</td>
                  <td class="px-2 py-1.5">
                    <div>{{ checkpointLabel(run.checkpoint) }}</div>
                    <div v-if="embeddingTelemetryLabel(run.checkpoint)" class="text-[11px] text-amber-600 dark:text-amber-300">
                      {{ embeddingTelemetryLabel(run.checkpoint) }}
                    </div>
                  </td>
                  <td class="px-2 py-1.5">
                    <div>{{ run.error_type || '-' }}</div>
                    <div v-if="run.error_message" class="text-[11px] text-slate-500 dark:text-slate-400" :title="run.error_message">
                      {{ compactErrorMessage(run.error_message) }}
                    </div>
                  </td>
                  <td class="px-2 py-1.5">
                    <div class="flex items-center gap-1.5">
                      <button
                        v-if="run.status === 'failed'"
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                        :disabled="docOpsLoading"
                        @click="retryTaskRun(run)"
                      >
                        Retry
                      </button>
                      <button
                        v-if="run.error_message"
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                        :disabled="docOpsLoading"
                        @click="copyRunError(run.error_message)"
                      >
                        Copy error
                      </button>
                      <span v-if="run.status !== 'failed' && !run.error_message" class="text-slate-400 dark:text-slate-500">-</span>
                    </div>
                  </td>
                </tr>
              </tbody>
              </table>
            </div>
          </template>
        </div>

        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800">
          <label class="inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-300">
            <input type="checkbox" v-model="docCleanupClearFirst" />
            Clear clean fields first
          </label>
          <div class="mt-2">
            <button
              class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              :disabled="docOpsLoading"
              title="Cleans stored page texts (e.g., line wraps or HTML noise) and updates clean fields."
              @click="runDocCleanup"
            >
              Cleanup page texts (this doc)
            </button>
          </div>
        </div>

        <div class="grid gap-2 md:grid-cols-2">
          <button
            v-for="action in operationActions"
            :key="action.task"
            class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            :disabled="docOpsLoading"
            :title="action.tooltip"
            @click="enqueueDocTask(action)"
          >
            {{ action.label }}
          </button>
        </div>

        <div class="rounded-lg border border-rose-200 bg-rose-50 p-3 dark:border-rose-900/50 dark:bg-rose-950/40">
          <button
            class="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-500"
            :disabled="docOpsLoading"
            title="Deletes local intelligence data for this document, resyncs from Paperless, and enqueues processing."
            @click="openResetConfirm"
          >
            Reset document + sync + full reprocess
          </button>
          <p class="mt-2 text-xs text-rose-700 dark:text-rose-200">
            Deletes local intelligence for this document, syncs from Paperless, then enqueues full processing.
          </p>
        </div>

        <div v-if="docOpsMessage" class="text-xs text-slate-500 dark:text-slate-300">
          {{ docOpsMessage }}
        </div>
      </section>

      <PdfViewer
        class="mt-6"
        :pdf-url="pdfUrl"
        v-model:page="pdfPage"
        :highlights="pdfHighlights"
        @update:page="onPdfPageChange"
      />

      <ConfirmDialog
        :open="resetConfirmOpen"
        title="Reset document and reprocess?"
        message="This deletes local intelligence data for this document, resyncs metadata/content from Paperless, and re-enqueues processing."
        confirm-label="Reset + Reprocess"
        @confirm="confirmResetAndReprocessDoc"
        @cancel="resetConfirmOpen = false"
      />
      <ConfirmDialog
        :open="writebackConfirmOpen"
        title="Write changes to Paperless?"
        message="This updates metadata and AI summary note in Paperless immediately for this document."
        confirm-label="Write now"
        cancel-label="Cancel"
        @confirm="confirmWritebackNow"
        @cancel="writebackConfirmOpen = false"
      />
      <div
        v-if="writebackConflictOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4"
      >
        <div
          class="w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
        >
          <div class="text-base font-semibold text-slate-900 dark:text-slate-100">
            Resolve writeback conflicts
          </div>
          <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">
            Paperless changed since this document was loaded. Choose how each field should be handled.
          </p>
          <div class="mt-4 space-y-3">
            <div
              v-for="conflict in writebackConflicts"
              :key="conflict.field"
              class="rounded-lg border border-slate-200 p-3 dark:border-slate-700"
            >
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {{ conflictFieldLabel(conflict.field) }}
              </div>
              <div class="mt-2 grid gap-3 md:grid-cols-2">
                <div>
                  <div class="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Paperless</div>
                  <div class="mt-1 whitespace-pre-wrap rounded-md bg-slate-50 p-2 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    {{ conflictValue(conflict.paperless) }}
                  </div>
                </div>
                <div>
                  <div class="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Local</div>
                  <div class="mt-1 whitespace-pre-wrap rounded-md bg-slate-50 p-2 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    {{ conflictValue(conflict.local) }}
                  </div>
                </div>
              </div>
              <div class="mt-3">
                <select
                  v-model="writebackResolutions[conflict.field]"
                  class="w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="skip">Skip</option>
                  <option value="use_paperless">Use Paperless (sync local)</option>
                  <option value="use_local">Use Local (writeback)</option>
                </select>
              </div>
            </div>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button
              class="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
              @click="cancelWritebackConflict"
            >
              Cancel
            </button>
            <button
              class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
              :disabled="writebackRunning"
              @click="applyWritebackConflictResolutions"
            >
              Apply decisions
            </button>
          </div>
        </div>
      </div>
      <ConfirmDialog
        :open="writebackErrorOpen"
        title="Writeback failed"
        :message="writebackErrorMessage || 'Unknown error'"
        confirm-label="Close"
        cancel-label="Close"
        @confirm="writebackErrorOpen = false"
        @cancel="writebackErrorOpen = false"
      />

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { AlertTriangle, ArrowLeft, CheckCircle, ClipboardCheck, ExternalLink, MinusCircle, RefreshCw } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import IconButton from '../components/IconButton.vue'
import DocumentMetadataSection from '../components/DocumentMetadataSection.vue'
import DocumentTextQualitySection from '../components/DocumentTextQualitySection.vue'
import DocumentSuggestionsSection from '../components/DocumentSuggestionsSection.vue'
import DocumentPagesSection from '../components/DocumentPagesSection.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PdfViewer from '../components/PdfViewer.vue'
import { useToastStore } from '../stores/toastStore'
import { useDocumentPipeline } from '../composables/useDocumentPipeline'
import { markDocumentReviewed, type DocumentOperationTaskPayload } from '../services/documents'
import { useDocumentOperations } from '../composables/useDocumentOperations'
import { useDocumentDetailData } from '../composables/useDocumentDetailData'
import { useAutoRefresh } from '../composables/useAutoRefresh'
import { usePaperlessBaseUrl } from '../composables/usePaperlessBaseUrl'
import { useDocumentTaskRuns } from '../composables/useDocumentTaskRuns'
import {
  fanoutStatusClass,
  processingBadgeClass,
  processingStateLabel,
  useDocumentProcessingState,
} from '../composables/useDocumentProcessingState'
import { executeWritebackDirectForDocument, type WritebackConflictField } from '../services/writeback'
import { consumeCitationJump } from '../services/citationJump'
import { conflictFieldLabel, conflictValue } from '../utils/writebackConflict'
import { formatDateTime, formatRelativeTime } from '../utils/dateTime'
import { formatCheckpointLabel } from '../utils/taskRunCheckpoint'
import {
  compactErrorMessage,
  embeddingTelemetryLabel,
  errorMessage,
  formatDocDate,
  parseBBox,
  queryToRecord,
  toDateTime,
  toTitle,
  type BBox,
} from '../utils/documentDetail'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const returnToDocumentsPath = computed(() => {
  const raw = route.query.return_to
  const encoded = Array.isArray(raw) ? raw[0] : raw
  if (typeof encoded !== 'string' || !encoded.trim()) return '/documents'
  try {
    const decoded = decodeURIComponent(encoded)
    if (decoded.startsWith('/documents')) return decoded
  } catch {
    // ignore malformed return path
  }
  return '/documents'
})

const toastStore = useToastStore()
const { paperlessBaseUrl } = usePaperlessBaseUrl()
const {
  document,
  loading,
  tags,
  correspondents,
  docTypes,
  pageTexts,
  pageTextsVisionProgress,
  pageTextsError,
  contentQuality,
  contentQualityError,
  ocrScores,
  ocrScoresLoading,
  ocrScoresError,
  suggestions,
  suggestionsLoading,
  suggestionsError,
  suggestionVariants,
  suggestionVariantLoading,
  suggestionVariantError,
  loadDocument,
  loadMeta,
  loadPageTexts,
  loadContentQuality,
  loadOcrScores,
  loadSuggestions,
  refreshSuggestions: refreshSuggestionsForSource,
  suggestField,
  applyVariant,
  applyToDocument: applySuggestionToDocument,
} = useDocumentDetailData()
const {
  pipelineStatus,
  pipelineStatusLoading,
  pipelineStatusError,
  pipelineFanout,
  pipelineFanoutLoading,
  pipelineFanoutError,
  refreshPipelineStatus,
  refreshPipelineFanout,
  continuePipeline: continuePipelineRequest,
  continuePipelineLoading,
} = useDocumentPipeline(computed(() => id))
const {
  loading: docOpsLoading,
  enqueueTask: enqueueDocumentTaskNow,
  cleanup: cleanupDocumentTexts,
  resetAndReprocess: resetAndReprocessNow,
} = useDocumentOperations(computed(() => id))
const timelineStatusFilter = ref('')
const timelineQueryFilter = ref('')
const {
  taskRuns,
  taskRunsLoading,
  taskRunsError,
  refreshTaskRuns,
} = useDocumentTaskRuns(() => id, {
  status: timelineStatusFilter,
  query: timelineQueryFilter,
})

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const pdfUrl = computed(() => `${apiBaseUrl}/documents/${id}/pdf`)
const pdfPage = ref(1)
const pdfHighlights = ref<BBox[]>([])
type DetailTabKey = 'meta' | 'text' | 'suggestions' | 'pages' | 'operations'
const tabs: Array<{ key: DetailTabKey; label: string }> = [
  { key: 'meta', label: 'Metadata' },
  { key: 'text', label: 'Text & quality' },
  { key: 'suggestions', label: 'Suggestions' },
  { key: 'pages', label: 'Pages' },
  { key: 'operations', label: 'Operations' },
]
type OperationAction = {
  task: Extract<
    DocumentOperationTaskPayload['task'],
    | 'vision_ocr'
    | 'embeddings_vision'
    | 'page_notes_vision'
    | 'summary_hierarchical'
    | 'suggestions_paperless'
    | 'suggestions_vision'
  >
  label: string
  tooltip: string
  force?: boolean
  source?: 'paperless_ocr' | 'vision_ocr'
}

const operationActions: OperationAction[] = [
  {
    task: 'vision_ocr',
    label: 'Queue vision OCR',
    tooltip: 'Triggers vision OCR again for pages of this document.',
    force: true,
  },
  {
    task: 'embeddings_vision',
    label: 'Queue embeddings (vision)',
    tooltip: 'Erstellt Embeddings aus Vision-OCR-Text und speichert sie in Qdrant.',
  },
  {
    task: 'page_notes_vision',
    label: 'Queue page notes (vision)',
    tooltip: 'Generates structured page notes from vision OCR per page.',
  },
  {
    task: 'summary_hierarchical',
    label: 'Queue hierarchical summary',
    tooltip: 'Aggregates page notes by section and builds a hierarchical summary.',
    source: 'vision_ocr',
  },
  {
    task: 'suggestions_paperless',
    label: 'Queue suggestions (paperless)',
    tooltip: 'Generates suggestion fields from Paperless OCR text.',
  },
  {
    task: 'suggestions_vision',
    label: 'Queue suggestions (vision)',
    tooltip: 'Generates suggestion fields from vision OCR text.',
  },
]
const activeTab = ref<DetailTabKey>('meta')
const reloadingAll = ref(false)
const reviewMarking = ref(false)
const docCleanupClearFirst = ref(false)
const docOpsMessage = ref('')
const resetConfirmOpen = ref(false)
const writebackRunning = ref(false)
const writebackConfirmOpen = ref(false)
const writebackConflictOpen = ref(false)
const writebackConflicts = ref<WritebackConflictField[]>([])
const writebackResolutions = ref<Record<string, 'skip' | 'use_paperless' | 'use_local'>>({})
const writebackErrorOpen = ref(false)
const writebackErrorMessage = ref('')
const continueQueuedWaiting = ref(false)
const continueQueuedExpireAt = ref(0)
const hasLocalWritebackChanges = computed(() => Boolean(document.value?.local_overrides))
const canWriteback = computed(() => {
  if (!document.value) return false
  return hasLocalWritebackChanges.value || document.value.review_status === 'needs_review'
})
const writebackButtonTitle = computed(() => {
  if (writebackRunning.value) return 'Writeback is currently running'
  if (canWriteback.value) return 'Write local changes back to Paperless'
  return 'No local changes detected for writeback'
})
const writebackButtonLabel = computed(() => {
  if (writebackRunning.value) return 'Writing back...'
  if (canWriteback.value) return 'Write back'
  return 'No changes to write back'
})
type TimelineTaskRun = {
  task: string
  source?: string | null
  status: string
}
const {
  processingStatusItems,
  processingRequiredCount,
  processingDoneCount,
  pipelineFanoutItems,
  activeRun,
  hasActiveTaskRuns,
  activeRunLabel,
  shouldAutoRefreshTimeline,
  pipelinePreferredSource,
  isLargeDocumentMode,
  largeDocumentHint,
} = useDocumentProcessingState(
  {
    pipelineStatus,
    pipelineFanout,
    taskRuns,
    continueQueuedWaiting,
  },
  checkpointLabel,
)

const paperlessUrl = computed(() =>
  paperlessBaseUrl.value && document.value
    ? `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${document.value.id}`
    : '',
)

const aggregatedText = computed(() => {
  if (!pageTexts.value.length) return document.value?.content || ''
  return pageTexts.value.map((page) => page.text).join('\n\n')
})

const suggestFieldAction = async (source: 'paperless_ocr' | 'vision_ocr', field: string) => {
  await suggestField(id, source, field)
}

const applyVariantOnly = async (
  source: 'paperless_ocr' | 'vision_ocr',
  field: string,
  value: unknown,
) => {
  await applyVariant(id, source, field, value)
}

const applyVariantToDocument = async (
  source: 'paperless_ocr' | 'vision_ocr',
  field: string,
  value: unknown,
) => {
  await applyVariant(id, source, field, value)
  await applySuggestionToDocument(id, { source, field, value })
  await load()
  await loadSuggestionsForDoc()
}

const applyToDocument = async (source: string, field: string, value: unknown) => {
  try {
    const reloadSuggestions = Boolean(suggestions.value)
    const reloadPages = pageTexts.value.length > 0
    const reloadQuality = Boolean(contentQuality.value)
    await applySuggestionToDocument(id, { source, field, value })
    await load()
    if (reloadSuggestions) {
      await loadSuggestionsForDoc()
    }
    if (reloadPages) {
      await loadPageTextsForDoc()
    }
    if (reloadQuality) {
      await loadContentQualityForDoc()
    }
  } catch (err: unknown) {
    suggestionsError.value = errorMessage(err, 'Failed to apply suggestion to document')
  }
}

const currentNotePreview = computed(() =>
  (document.value?.notes || [])
    .map((note) => note.note)
    .filter(Boolean)
    .join(' ')
    .trim(),
)

const currentTagNames = computed(() =>
  (document.value?.tags || [])
    .map((tagId) => tags.value.find((tag) => tag.id === tagId)?.name ?? tagId)
    .join(', '),
)

const currentCorrespondentName = computed(() => {
  if (!document.value) return ''
  const value =
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent ??
    ''
  return String(value)
})

const currentValues = computed(() => ({
  title: document.value?.title || '',
  date: formatDocDate(document.value?.document_date || document.value?.created) || '',
  correspondent: currentCorrespondentName.value || '',
  tags: currentTagNames.value || '',
  note: currentNotePreview.value || '',
}))
const canMarkReviewed = computed(
  () =>
    Boolean(document.value) &&
    !document.value?.local_overrides &&
    String(document.value?.review_status || '').toLowerCase() !== 'reviewed',
)

const rows = computed(() => {
  if (!document.value) return []
  const notes = (document.value.notes || []).map((n) => n.note).join(' ')
  const tagNames = (document.value.tags || [])
    .map((tagId) => tags.value.find((t) => t.id === tagId)?.name ?? tagId)
    .join(', ')
  const pendingTagNames = (document.value.pending_tag_names || []).join(', ')
  const correspondentName =
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent
  const docTypeName =
    document.value.document_type_name ??
    docTypes.value.find((d) => d.id === document.value?.document_type)?.name ??
    document.value.document_type
  const createdLabel = formatDateTime(document.value.created) || '-'
  const modifiedLabel = formatDateTime(document.value.modified) || '-'
  return [
    { label: 'Title', value: document.value.title },
    { label: 'Issue date', value: formatDocDate(document.value.document_date || document.value.created) },
    { label: 'Correspondent', value: correspondentName },
    { label: 'Document type', value: docTypeName },
    { label: 'Tags', value: tagNames, pendingValue: pendingTagNames || null },
    {
      label: 'Original filename',
      value: document.value.original_file_name,
      className: 'md:col-span-2',
    },
    {
      label: 'Timestamps',
      value: `Created: ${createdLabel}\nModified: ${modifiedLabel}`,
    },
    { label: 'Notes', value: notes },
  ]
})

const headerMetaLine = computed(() => {
  const syncAt = formatDateTime(document.value?.modified)
  const reviewStatus = toTitle(document.value?.review_status || '')
  const reviewedAt = formatDateTime(document.value?.reviewed_at)
  const reviewPart = reviewedAt ? `${reviewStatus} (${reviewedAt})` : reviewStatus
  return `Document ID: ${id}, Synced at: ${syncAt || '-'}, ${reviewPart || 'Unknown'}`
})

const syncPdfFromQuery = () => {
  const jump = consumeCitationJump(route.query.jump)
  if (route.query.jump !== undefined) {
    const nextQuery = queryToRecord(route.query, ['jump'])
    void router.replace({ query: nextQuery })
  }
  const pageValue = Number(jump?.page ?? route.query.page)
  if (Number.isFinite(pageValue) && pageValue > 0) {
    pdfPage.value = pageValue
  }
  const bbox = parseBBox(jump?.bbox ?? route.query.bbox)
  pdfHighlights.value = bbox ? [bbox] : []
}

const normalizeTabQuery = (value: unknown): DetailTabKey => {
  const raw = Array.isArray(value) ? value[0] : value
  if (raw === 'text' || raw === 'suggestions' || raw === 'pages' || raw === 'operations') {
    return raw
  }
  return 'meta'
}

const syncTabFromQuery = () => {
  activeTab.value = normalizeTabQuery(route.query.tab)
}

const syncTabToQuery = async () => {
  const current = normalizeTabQuery(route.query.tab)
  if (current === activeTab.value) return
  const nextQuery = queryToRecord(route.query)
  if (activeTab.value === 'meta') {
    delete nextQuery.tab
  } else {
    nextQuery.tab = activeTab.value
  }
  await router.replace({ query: nextQuery })
}

const onPdfPageChange = (value: number) => {
  pdfPage.value = value
  const nextQuery = queryToRecord(route.query)
  nextQuery.page = String(value)
  delete nextQuery.bbox
  router.replace({ query: nextQuery })
  pdfHighlights.value = []
}

const navigateBackToDocuments = async () => {
  await router.push(returnToDocumentsPath.value)
}

const runWritebackNowForDocument = async (
  resolutions?: Record<string, 'skip' | 'use_paperless' | 'use_local'>,
) => {
  writebackRunning.value = true
  writebackErrorMessage.value = ''
  try {
    const result = await executeWritebackDirectForDocument(id, {
      known_paperless_modified: document.value?.paperless_modified ?? null,
      resolutions: resolutions ?? {},
    })
    if (result.status === 'conflicts') {
      writebackConflicts.value = result.conflicts || []
      writebackResolutions.value = Object.fromEntries(
        writebackConflicts.value.map((conflict) => [conflict.field, 'skip']),
      ) as Record<string, 'skip' | 'use_paperless' | 'use_local'>
      writebackConflictOpen.value = true
      toastStore.push(
        'Conflicts detected. Choose per field how to proceed.',
        'warning',
        'Writeback',
        3000,
      )
      return
    }
    const calls = result.calls_count ?? 0
    const changed = result.docs_changed ?? 0
    if (calls > 0 && changed > 0) {
      toastStore.push(
        `Writeback executed ${calls} call(s) for ${changed} changed document(s).`,
        'success',
        'Writeback',
        2200,
      )
    } else {
      toastStore.push(
        'No writeback changes found for this document.',
        'info',
        'Writeback',
        2200,
      )
    }
    await reloadAll()
  } catch (err: unknown) {
    const message = errorMessage(err, 'Failed to write back document')
    toastStore.push(message, 'danger', 'Writeback', 2800)
    writebackErrorMessage.value = message
    writebackErrorOpen.value = true
  } finally {
    writebackRunning.value = false
  }
}

const markReviewedAction = async () => {
  if (!canMarkReviewed.value || reviewMarking.value) return
  reviewMarking.value = true
  try {
    const result = await markDocumentReviewed(id)
    if (result.status === 'missing') {
      toastStore.push('Document not found locally.', 'warning', 'Review', 2200)
      return
    }
    await load()
    toastStore.push('Document marked as reviewed.', 'success', 'Review', 1800)
  } catch (err: unknown) {
    toastStore.push(errorMessage(err, 'Failed to mark document reviewed'), 'danger', 'Review', 2800)
  } finally {
    reviewMarking.value = false
  }
}

const openWritebackConfirm = () => {
  if (!canWriteback.value || writebackRunning.value) return
  writebackConfirmOpen.value = true
}

const confirmWritebackNow = async () => {
  writebackConfirmOpen.value = false
  await runWritebackNowForDocument()
}

const cancelWritebackConflict = () => {
  writebackConflictOpen.value = false
  writebackConflicts.value = []
  writebackResolutions.value = {}
}

const applyWritebackConflictResolutions = async () => {
  writebackConflictOpen.value = false
  await runWritebackNowForDocument({ ...writebackResolutions.value })
  writebackConflicts.value = []
  writebackResolutions.value = {}
}

const toRelativeTime = (value?: string | null) => {
  return formatRelativeTime(value)
}

function checkpointLabel(checkpoint?: Record<string, unknown> | null) {
  return formatCheckpointLabel(checkpoint, '-')
}

const copyRunError = async (message?: string | null) => {
  const text = String(message || '').trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toastStore.push('Error copied to clipboard.', 'success', 'Processing timeline', 1800)
  } catch {
    toastStore.push('Failed to copy error message.', 'danger', 'Processing timeline', 2400)
  }
}

const load = async () => {
  await loadDocument(id)
}

const loadMetaForDoc = async () => {
  await loadMeta()
}

const loadPageTextsForDoc = async (priority = false) => {
  await loadPageTexts(id, priority)
}

const loadContentQualityForDoc = async (priority = false) => {
  await loadContentQuality(id, priority)
  await loadOcrScores(id, priority)
}

const loadSuggestionsForDoc = async () => {
  await loadSuggestions(id)
}

const loadPipelineStatus = async () => {
  await refreshPipelineStatus()
}

const loadPipelineFanout = async () => {
  await refreshPipelineFanout()
}

const reloadPipelineFanout = async () => {
  await loadPipelineFanout()
}

const withDocOperation = async (fn: () => Promise<void>) => {
  docOpsMessage.value = ''
  await fn()
  await loadPipelineStatus()
  await loadPipelineFanout()
}

const reloadAll = async () => {
  reloadingAll.value = true
  try {
    await load()
    await loadMetaForDoc()
    await loadContentQualityForDoc()
    await loadPageTextsForDoc()
    await loadSuggestionsForDoc()
    await loadPipelineStatus()
    await loadPipelineFanout()
  } finally {
    reloadingAll.value = false
  }
}

const refreshSuggestionsAction = async (source: 'paperless_ocr' | 'vision_ocr') => {
  await refreshSuggestionsForSource(id, source)
}

const enqueueDocTask = async (action: OperationAction) => {
  await withDocOperation(async () => {
    try {
      const result = await enqueueDocumentTaskNow({
        task: action.task,
        force: action.force ?? false,
        source: action.source,
      })
      docOpsMessage.value = result.enqueued
        ? `Queued task ${action.task} for document ${id}.`
        : `Task ${action.task} was not enqueued (possibly duplicate/running).`
    } catch (err) {
      docOpsMessage.value = errorMessage(err, `Failed to queue ${action.task}`)
    }
  })
}

const retryTaskRun = async (run: TimelineTaskRun) => {
  const task = String(run.task || '').trim() as DocumentOperationTaskPayload['task']
  if (!task) return
  await withDocOperation(async () => {
    try {
      const result = await enqueueDocumentTaskNow({
        task,
        source: run.source === 'paperless_ocr' || run.source === 'vision_ocr' ? run.source : undefined,
      })
      docOpsMessage.value = result.enqueued
        ? `Queued retry for ${task}.`
        : `Retry for ${task} was not enqueued (duplicate or already running).`
      await refreshTaskRuns()
    } catch (err) {
      docOpsMessage.value = errorMessage(err, `Failed to retry ${task}`)
    }
  })
}

const runDocCleanup = async () => {
  await withDocOperation(async () => {
    try {
      const result = await cleanupDocumentTexts(docCleanupClearFirst.value)
      docOpsMessage.value = result.queued
        ? `Queued cleanup for ${result.docs} document(s).`
        : `Cleanup done: ${result.updated}/${result.processed} updated.`
    } catch (err) {
      docOpsMessage.value = errorMessage(err, 'Failed to queue cleanup')
    }
  })
}

const runContinuePipeline = async () => {
  await withDocOperation(async () => {
    try {
      continueQueuedWaiting.value = false
      continueQueuedExpireAt.value = 0
      const result = await continuePipelineRequest({
        include_vision_ocr: true,
        include_embeddings: true,
        include_embeddings_paperless: true,
        include_embeddings_vision: true,
        include_page_notes: true,
        include_summary_hierarchical: true,
        include_suggestions_paperless: true,
        include_suggestions_vision: true,
      })
      if (!result.enabled) {
        docOpsMessage.value = 'Queue is disabled.'
        return
      }
      docOpsMessage.value = result.enqueued
        ? `Enqueued ${result.enqueued}/${result.missing_tasks} missing tasks.`
        : `No missing tasks.`
      if ((result.enqueued || 0) > 0) {
        continueQueuedWaiting.value = true
        continueQueuedExpireAt.value = Date.now() + 120_000
        await Promise.all([refreshTaskRuns(), loadPipelineStatus(), refreshPipelineFanout()])
      }
    } catch (err) {
      docOpsMessage.value = errorMessage(err, 'Failed to continue document pipeline')
      continueQueuedWaiting.value = false
      continueQueuedExpireAt.value = 0
    }
  })
}

const runResetAndReprocessDoc = async () => {
  await withDocOperation(async () => {
    try {
      const result = await resetAndReprocessNow(true)
      docOpsMessage.value = `Document reset/synced. Enqueued ${result.enqueued} tasks.`
      await load()
    } catch (err) {
      docOpsMessage.value = errorMessage(err, 'Failed to reset and reprocess document')
    }
  })
}

const openResetConfirm = () => {
  resetConfirmOpen.value = true
}

const confirmResetAndReprocessDoc = async () => {
  resetConfirmOpen.value = false
  await runResetAndReprocessDoc()
}

useAutoRefresh({
  enabled: shouldAutoRefreshTimeline,
  intervalMs: 5000,
  onTick: async () => {
    if (continueQueuedWaiting.value && continueQueuedExpireAt.value > 0 && Date.now() >= continueQueuedExpireAt.value) {
      continueQueuedWaiting.value = false
      continueQueuedExpireAt.value = 0
    }
    await refreshTaskRuns()
    await loadPipelineStatus()
    await refreshPipelineFanout()
  },
})

watch(
  activeRun,
  (run) => {
    if (run && continueQueuedWaiting.value) {
      continueQueuedWaiting.value = false
      continueQueuedExpireAt.value = 0
    }
  },
)

onMounted(async () => {
  syncTabFromQuery()
  syncPdfFromQuery()
  await reloadAll()
})

watch(
  () => route.query,
  () => {
    syncTabFromQuery()
    syncPdfFromQuery()
  },
)

watch(
  activeTab,
  async () => {
    await syncTabToQuery()
  },
)

</script>
