<template>
  <section>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          {{ document?.title || `Document ${id}` }}
        </h2>
        <p class="text-sm text-slate-500 dark:text-slate-400">Document ID: {{ id }}</p>
      </div>
      <div class="flex items-center gap-2">
        <IconButton
          v-if="paperlessUrl"
          :href="paperlessUrl"
          title="View document in Paperless"
          aria-label="View document in Paperless"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <IconButton
          v-else
          disabled
          title="Set VITE_PAPERLESS_BASE_URL to enable"
          aria-label="Paperless link unavailable"
        >
          <ExternalLink class="h-5 w-5" />
        </IconButton>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800"
          @click="load"
        >
          <RefreshCw class="h-4 w-4" />
          Reload
        </button>
      </div>
    </div>

    <section
      class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-center gap-3">
        <div
          class="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300"
        >
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doResync" />
            Resync
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doReembed" :disabled="!doResync" />
            Re-embed
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doQuality" />
            Analyze quality
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doPages" />
            Load extracted pages
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="doSuggestions" />
            Generate suggestions
          </label>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
          :disabled="processing"
          @click="runReprocess"
        >
          <RefreshCcw class="h-4 w-4" />
          {{ processing ? 'Processing...' : 'Re-process' }}
        </button>
      </div>
    </section>

    <div v-if="loading" class="mt-6 text-sm text-slate-500">Loading...</div>
    <div v-else class="mt-6 space-y-4">
      <div
        class="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 text-xs font-semibold text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
      >
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

      <section
        v-if="activeTab === 'meta'"
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

      <section
        v-if="activeTab === 'text'"
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Text layer</h3>
          <span class="text-xs font-semibold text-slate-500 dark:text-slate-400">Baseline OCR</span>
        </div>
        <textarea
          class="mt-4 w-full min-h-[260px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          readonly
          :value="document?.content || ''"
        ></textarea>

        <div
          class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Text quality (baseline)
            </div>
            <span
              v-if="contentQuality"
              class="rounded-full px-2 py-1 text-xs font-semibold"
              :class="
                contentQuality.score >= 80
                  ? 'bg-emerald-100 text-emerald-700'
                  : contentQuality.score >= 60
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-rose-100 text-rose-700'
              "
            >
              Score {{ contentQuality.score }}
            </span>
          </div>
          <div v-if="contentQualityError" class="mt-2 text-sm text-rose-600 dark:text-rose-300">
            {{ contentQualityError }}
          </div>
          <div v-else-if="!contentQuality" class="mt-2 text-sm text-slate-500 dark:text-slate-400">
            No quality metrics loaded.
          </div>
          <div v-else class="mt-3 text-xs text-slate-600 dark:text-slate-300">
            <div v-if="contentQuality.reasons?.length" class="mt-1">
              Reasons: {{ contentQuality.reasons.join(', ') }}
            </div>
            <details class="mt-3">
              <summary class="cursor-pointer text-xs font-semibold text-slate-500">
                Show metrics
              </summary>
              <div class="mt-2 grid gap-2 md:grid-cols-3">
                <div
                  v-for="(value, key) in contentQuality.metrics"
                  :key="key"
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                >
                  {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
                </div>
              </div>
            </details>
          </div>
        </div>
      </section>

      <section
        v-if="activeTab === 'suggestions'"
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">AI suggestions</h3>
          <span class="text-xs text-slate-500 dark:text-slate-400"
            >Paperless OCR ? Vision OCR ? Best pick</span
          >
        </div>
        <div
          v-if="suggestionsError"
          class="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
        >
          {{ suggestionsError }}
        </div>
        <div v-else-if="!suggestions" class="mt-3 text-sm text-slate-500 dark:text-slate-400">
          No suggestions loaded.
        </div>
        <div v-else class="mt-4 space-y-4">
          <div
            class="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
          >
            <div class="flex items-center justify-between">
              <strong class="text-sm text-slate-900 dark:text-slate-100">Best pick</strong>
            </div>
            <div v-if="!bestPickSuggestion" class="mt-3 text-sm text-slate-500 dark:text-slate-400">
              <em>No data.</em>
            </div>
            <div v-else class="mt-3 space-y-3">
              <div v-if="bestPickSuggestion.raw">
                <div class="text-xs font-semibold text-slate-500">Raw output</div>
                <pre
                  class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  >{{ bestPickSuggestion.raw }}</pre
                >
              </div>
              <div v-if="bestPickSuggestion.data" class="space-y-2">
                <div
                  class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400"
                >
                  <span>Summary</span>
                  <button
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                    @click="applyToDocument('best_pick', 'note', bestPickSuggestion.data)"
                  >
                    Save note
                  </button>
                </div>
                <div class="text-sm text-slate-900 dark:text-slate-100">
                  {{ bestPickSuggestion.data.summary }}
                </div>
                <div class="grid gap-2">
                  <div
                    class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400"
                  >
                    <span>Document type</span>
                    <span class="text-slate-900 dark:text-slate-100">{{
                      bestPickSuggestion.data.documentType
                    }}</span>
                  </div>
                  <div
                    class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400"
                  >
                    <span>Language</span>
                    <span class="text-slate-900 dark:text-slate-100">{{
                      bestPickSuggestion.data.language
                    }}</span>
                  </div>
                </div>
                <div
                  v-for="field in suggestionFields"
                  :key="`best-${field.key}`"
                  class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]"
                >
                  <span class="text-xs text-slate-500 dark:text-slate-400">{{ field.label }}</span>
                  <div class="text-sm text-slate-900 dark:text-slate-100">
                    <template v-if="field.key === 'tags'">
                      <div
                        v-if="normalizedTags(bestPickSuggestion.data).length"
                        class="flex flex-wrap gap-1.5"
                      >
                        <span
                          v-for="tag in normalizedTags(bestPickSuggestion.data)"
                          :key="`best-tag-${tag}`"
                          class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                        >
                          {{ tag }}
                        </span>
                      </div>
                      <span v-else class="text-xs text-slate-400 dark:text-slate-500"
                        >No tags suggested</span
                      >
                    </template>
                    <template v-else>
                      {{ fieldValue(bestPickSuggestion.data, field.key) }}
                    </template>
                  </div>
                  <button
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                    @click="applyToDocument('best_pick', field.key, bestPickSuggestion.data)"
                  >
                    Save
                  </button>
                </div>
                <div
                  v-if="
                    (bestPickSuggestion.data.suggested_tags_existing || []).length ||
                    (bestPickSuggestion.data.suggested_tags_new || []).length
                  "
                  class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                >
                  <div>
                    Existing tags:
                    {{ (bestPickSuggestion.data.suggested_tags_existing || []).join(', ') }}
                  </div>
                  <div>
                    New tags: {{ (bestPickSuggestion.data.suggested_tags_new || []).join(', ') }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div
              class="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
            >
              <div class="flex items-center justify-between">
                <strong class="text-sm text-slate-900 dark:text-slate-100">Paperless OCR</strong>
                <button
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                  :disabled="suggestionsLoading"
                  @click="refreshSuggestions('paperless_ocr')"
                >
                  Refresh
                </button>
              </div>
              <div
                v-if="suggestionMetaLine('paperless_ocr')"
                class="mt-2 text-xs text-slate-500 dark:text-slate-400"
              >
                {{ suggestionMetaLine('paperless_ocr') }}
              </div>
              <div
                v-if="!paperlessSuggestion"
                class="mt-3 text-sm text-slate-500 dark:text-slate-400"
              >
                <em>No data.</em>
              </div>
              <div v-else class="mt-3 space-y-3">
                <div v-if="paperlessSuggestion.raw">
                  <div class="text-xs font-semibold text-slate-500">Raw output</div>
                  <pre
                    class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                    >{{ paperlessSuggestion.raw }}</pre
                  >
                </div>
                <div v-if="paperlessSuggestion.data" class="space-y-2">
                  <div class="text-xs text-slate-500 dark:text-slate-400">Summary</div>
                  <div class="text-sm text-slate-900 dark:text-slate-100">
                    {{ paperlessSuggestion.data.summary }}
                  </div>
                  <div class="grid gap-2">
                    <div
                      class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400"
                    >
                      <span>Document type</span>
                      <span class="text-slate-900 dark:text-slate-100">{{
                        paperlessSuggestion.data.documentType ||
                        paperlessSuggestion.data.suggested_document_type
                      }}</span>
                    </div>
                    <div
                      class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400"
                    >
                      <span>Language</span>
                      <span class="text-slate-900 dark:text-slate-100">{{
                        paperlessSuggestion.data.language
                      }}</span>
                    </div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`paperless-${field.key}`"
                    class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]"
                  >
                    <span class="text-xs text-slate-500 dark:text-slate-400">{{
                      field.label
                    }}</span>
                    <div class="text-sm text-slate-900 dark:text-slate-100">
                      <template v-if="field.key === 'tags'">
                        <div
                          v-if="normalizedTags(paperlessSuggestion.data).length"
                          class="flex flex-wrap gap-1.5"
                        >
                          <span
                            v-for="tag in normalizedTags(paperlessSuggestion.data)"
                            :key="`paperless-tag-${tag}`"
                            class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                          >
                            {{ tag }}
                          </span>
                        </div>
                        <span v-else class="text-xs text-slate-400 dark:text-slate-500"
                          >No tags suggested</span
                        >
                      </template>
                      <template v-else>
                        {{ fieldValue(paperlessSuggestion.data, field.key) }}
                      </template>
                    </div>
                    <div class="flex items-center gap-2">
                      <button
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                        :disabled="suggestionVariantLoading[`paperless_ocr:${field.key}`]"
                        @click="suggestField('paperless_ocr', field.key)"
                      >
                        Suggest new
                      </button>
                      <button
                        class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                        @click="
                          applyToDocument('paperless_ocr', field.key, paperlessSuggestion.data)
                        "
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div
                    v-if="
                      (paperlessSuggestion.data.suggested_tags_existing || []).length ||
                      (paperlessSuggestion.data.suggested_tags_new || []).length
                    "
                    class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  >
                    <div>
                      Existing tags:
                      {{ (paperlessSuggestion.data.suggested_tags_existing || []).join(', ') }}
                    </div>
                    <div>
                      New tags: {{ (paperlessSuggestion.data.suggested_tags_new || []).join(', ') }}
                    </div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`paperless-variants-${field.key}`"
                    class="rounded-md border border-dashed border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900"
                  >
                    <div
                      v-if="suggestionVariantError[`paperless_ocr:${field.key}`]"
                      class="text-xs text-rose-600"
                    >
                      {{ suggestionVariantError[`paperless_ocr:${field.key}`] }}
                    </div>
                    <div v-if="(suggestionVariants[`paperless_ocr:${field.key}`] || []).length">
                      <div class="text-xs font-semibold text-slate-500">
                        Variants for {{ field.label }}
                      </div>
                      <div
                        v-for="variant in suggestionVariants[`paperless_ocr:${field.key}`]"
                        :key="`${field.key}-${variant}`"
                        class="mt-1 flex items-center justify-between gap-2 text-xs"
                      >
                        <span class="text-slate-700">{{
                          Array.isArray(variant) ? variant.join(', ') : variant
                        }}</span>
                        <button
                          class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-500"
                          @click="applyVariant('paperless_ocr', field.key, variant)"
                        >
                          Use
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div
              class="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
            >
              <div class="flex items-center justify-between">
                <strong class="text-sm text-slate-900 dark:text-slate-100">Vision OCR</strong>
                <button
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                  :disabled="suggestionsLoading"
                  @click="refreshSuggestions('vision_ocr')"
                >
                  Refresh
                </button>
              </div>
              <div
                v-if="suggestionMetaLine('vision_ocr')"
                class="mt-2 text-xs text-slate-500 dark:text-slate-400"
              >
                {{ suggestionMetaLine('vision_ocr') }}
              </div>
              <div v-if="!visionSuggestion" class="mt-3 text-sm text-slate-500 dark:text-slate-400">
                <em>No data.</em>
              </div>
              <div v-else class="mt-3 space-y-3">
                <div v-if="visionSuggestion.raw">
                  <div class="text-xs font-semibold text-slate-500">Raw output</div>
                  <pre
                    class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                    >{{ visionSuggestion.raw }}</pre
                  >
                </div>
                <div v-if="visionSuggestion.data" class="space-y-2">
                  <div class="text-xs text-slate-500 dark:text-slate-400">Summary</div>
                  <div class="text-sm text-slate-900 dark:text-slate-100">
                    {{ visionSuggestion.data.summary }}
                  </div>
                  <div class="grid gap-2">
                    <div
                      class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400"
                    >
                      <span>Document type</span>
                      <span class="text-slate-900 dark:text-slate-100">{{
                        visionSuggestion.data.documentType ||
                        visionSuggestion.data.suggested_document_type
                      }}</span>
                    </div>
                    <div
                      class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400"
                    >
                      <span>Language</span>
                      <span class="text-slate-900 dark:text-slate-100">{{
                        visionSuggestion.data.language
                      }}</span>
                    </div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`vision-${field.key}`"
                    class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]"
                  >
                    <span class="text-xs text-slate-500 dark:text-slate-400">{{
                      field.label
                    }}</span>
                    <div class="text-sm text-slate-900 dark:text-slate-100">
                      <template v-if="field.key === 'tags'">
                        <div
                          v-if="normalizedTags(visionSuggestion.data).length"
                          class="flex flex-wrap gap-1.5"
                        >
                          <span
                            v-for="tag in normalizedTags(visionSuggestion.data)"
                            :key="`vision-tag-${tag}`"
                            class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                          >
                            {{ tag }}
                          </span>
                        </div>
                        <span v-else class="text-xs text-slate-400 dark:text-slate-500"
                          >No tags suggested</span
                        >
                      </template>
                      <template v-else>
                        {{ fieldValue(visionSuggestion.data, field.key) }}
                      </template>
                    </div>
                    <div class="flex items-center gap-2">
                      <button
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                        :disabled="suggestionVariantLoading[`vision_ocr:${field.key}`]"
                        @click="suggestField('vision_ocr', field.key)"
                      >
                        Suggest new
                      </button>
                      <button
                        class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                        @click="applyToDocument('vision_ocr', field.key, visionSuggestion.data)"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div
                    v-if="
                      (visionSuggestion.data.suggested_tags_existing || []).length ||
                      (visionSuggestion.data.suggested_tags_new || []).length
                    "
                    class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  >
                    <div>
                      Existing tags:
                      {{ (visionSuggestion.data.suggested_tags_existing || []).join(', ') }}
                    </div>
                    <div>
                      New tags: {{ (visionSuggestion.data.suggested_tags_new || []).join(', ') }}
                    </div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`vision-variants-${field.key}`"
                    class="rounded-md border border-dashed border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900"
                  >
                    <div
                      v-if="suggestionVariantError[`vision_ocr:${field.key}`]"
                      class="text-xs text-rose-600"
                    >
                      {{ suggestionVariantError[`vision_ocr:${field.key}`] }}
                    </div>
                    <div v-if="(suggestionVariants[`vision_ocr:${field.key}`] || []).length">
                      <div class="text-xs font-semibold text-slate-500">
                        Variants for {{ field.label }}
                      </div>
                      <div
                        v-for="variant in suggestionVariants[`vision_ocr:${field.key}`]"
                        :key="`${field.key}-${variant}`"
                        class="mt-1 flex items-center justify-between gap-2 text-xs"
                      >
                        <span class="text-slate-700">{{
                          Array.isArray(variant) ? variant.join(', ') : variant
                        }}</span>
                        <button
                          class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-500"
                          @click="applyVariant('vision_ocr', field.key, variant)"
                        >
                          Use
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        v-if="activeTab === 'pages'"
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Extracted page texts (debug)
          </h3>
          <span class="text-xs text-slate-500 dark:text-slate-400">Page-wise OCR</span>
        </div>
        <div class="mt-4">
          <div
            class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
          >
            Aggregated text context
          </div>
          <textarea
            class="mt-2 w-full min-h-[180px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            readonly
            :value="aggregatedText"
          ></textarea>
        </div>
        <div v-if="pageTextsError" class="mt-3 text-sm text-rose-600 dark:text-rose-300">
          {{ pageTextsError }}
        </div>
        <div
          v-else-if="pageTexts.length === 0"
          class="mt-3 text-sm text-slate-500 dark:text-slate-400"
        >
          No extracted page text loaded.
        </div>
        <div v-else class="mt-4 space-y-4">
          <div
            v-for="page in pageTexts"
            :key="page.page"
            class="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
          >
            <div
              class="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400"
            >
              <span>Page {{ page.page }} - Source: {{ page.source }}</span>
              <button
                class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                @click="togglePage(page)"
              >
                {{ isExpanded(page) ? 'Hide' : 'Show' }}
              </button>
            </div>
            <div v-if="isExpanded(page)">
              <div v-if="page.quality" class="mt-2 text-xs text-slate-600 dark:text-slate-300">
                <div class="font-semibold text-slate-700 dark:text-slate-200">
                  Quality score: {{ page.quality.score }}
                </div>
                <div v-if="page.quality.reasons?.length" class="mt-1">
                  Reasons: {{ page.quality.reasons.join(', ') }}
                </div>
                <div class="mt-3 grid gap-2 md:grid-cols-3">
                  <div
                    v-for="(value, key) in page.quality.metrics"
                    :key="key"
                    class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  >
                    {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
                  </div>
                </div>
              </div>
              <div class="mt-3 grid gap-3 lg:grid-cols-[minmax(0,360px)_1fr]">
                <textarea
                  class="w-full min-h-[140px] rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  readonly
                  :value="page.text"
                ></textarea>
              </div>
            </div>
          </div>
        </div>
      </section>

      <PdfViewer
        class="mt-6"
        :pdf-url="pdfUrl"
        v-model:page="pdfPage"
        :highlights="pdfHighlights"
        @update:page="onPdfPageChange"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ExternalLink, RefreshCcw, RefreshCw } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import IconButton from '../components/IconButton.vue'
import PdfViewer from '../components/PdfViewer.vue'
import { useDocumentDetailStore } from '../stores/documentDetailStore'
import { useQueueStore } from '../stores/queueStore'
import { useToastStore } from '../stores/toastStore'
import { useStatusStore } from '../stores/statusStore'
import { PageText } from '../services/documents'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)

const documentStore = useDocumentDetailStore()
const queueStore = useQueueStore()
const toastStore = useToastStore()
const statusStore = useStatusStore()
const {
  document,
  loading,
  tags,
  correspondents,
  docTypes,
  pageTexts,
  pageTextsLoading,
  pageTextsError,
  contentQuality,
  contentQualityLoading,
  contentQualityError,
  suggestions,
  suggestionsLoading,
  suggestionsError,
  suggestionVariants,
  suggestionVariantLoading,
  suggestionVariantError,
} = storeToRefs(documentStore)

const processing = ref(false)
const doResync = ref(true)
const doReembed = ref(true)
const doQuality = ref(true)
const doPages = ref(true)
const doSuggestions = ref(true)
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const pdfUrl = computed(() => `${apiBaseUrl}/documents/${id}/pdf`)
const pdfPage = ref(1)
const pdfHighlights = ref<number[][]>([])
const tabs = [
  { key: 'meta', label: 'Metadata' },
  { key: 'text', label: 'Text & quality' },
  { key: 'suggestions', label: 'Suggestions' },
  { key: 'pages', label: 'Pages' },
]
const activeTab = ref('meta')

const parseBBox = (value: unknown): number[] | null => {
  if (!value) return null
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'string') return null
  const parts = raw.split(',').map((part) => Number(part.trim()))
  if (parts.length !== 4 || parts.some((v) => Number.isNaN(v))) return null
  return parts as number[]
}
const expandedPages = ref<Set<string>>(new Set())

const paperlessBaseUrl = computed(
  () => import.meta.env.VITE_PAPERLESS_BASE_URL || statusStore.paperlessBaseUrl || '',
)
const paperlessUrl = computed(() =>
  paperlessBaseUrl.value && document.value
    ? `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${document.value.id}`
    : '',
)

const normalizeSuggestion = (input: any) => {
  if (!input || (typeof input === 'object' && Object.keys(input).length === 0)) {
    return null
  }
  const raw = input.raw || null
  const data = input.parsed || (raw ? null : input)
  return { raw, data }
}

const paperlessSuggestion = computed(() => normalizeSuggestion(suggestions.value?.paperless_ocr))
const visionSuggestion = computed(() => normalizeSuggestion(suggestions.value?.vision_ocr))
const bestPickSuggestion = computed(() => normalizeSuggestion(suggestions.value?.best_pick))
const suggestionsMeta = computed(() => (suggestions.value as any)?.suggestions_meta || {})
const suggestionFields = [
  { key: 'title', label: 'Suggested title' },
  { key: 'date', label: 'Suggested date' },
  { key: 'correspondent', label: 'Suggested correspondent' },
  { key: 'tags', label: 'Suggested tags' },
]

const suggestionMetaLine = (source: string) => {
  const meta = suggestionsMeta.value?.[source]
  if (!meta) return ''
  const model = meta.model || 'unknown'
  const processed = meta.processed_at ? formatDateTime(meta.processed_at) : 'unknown'
  return `Model: ${model} · Updated: ${processed}`
}

const aggregatedText = computed(() => {
  if (!pageTexts.value.length) return document.value?.content || ''
  return pageTexts.value.map((page) => page.text).join('\n\n')
})

const fieldValue = (data: any, field: string) => {
  if (!data) return ''
  if (field === 'title') return data.title || data.suggested_title
  if (field === 'date') return data.date || data.suggested_document_date
  if (field === 'correspondent') return data.correspondent || data.suggested_correspondent
  if (field === 'tags') return data.tags || data.suggested_tags
  return data[field]
}

const normalizedTags = (data: any): string[] => {
  const raw = fieldValue(data, 'tags')
  if (!raw) return []
  if (Array.isArray(raw)) return raw.map((tag) => String(tag)).filter(Boolean)
  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        const parsed = JSON.parse(trimmed)
        if (Array.isArray(parsed)) {
          return parsed.map((tag) => String(tag)).filter(Boolean)
        }
      } catch {
        // fall through to splitting
      }
    }
    return trimmed
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean)
  }
  return [String(raw)]
}

const suggestField = async (source: 'paperless_ocr' | 'vision_ocr', field: string) => {
  await documentStore.suggestField(id, source, field)
}

const applyVariant = async (source: 'paperless_ocr' | 'vision_ocr', field: string, value: any) => {
  const label = typeof value === 'string' ? value : JSON.stringify(value)
  const ok = window.confirm(`Overwrite ${field} with: ${label}?`)
  if (!ok) return
  await documentStore.applyVariant(id, source, field, value)
}

const applyToDocument = async (source: string, field: string, data: any) => {
  if (!data) return
  let value: any = data[field]
  if (field === 'title') value = data.title || data.suggested_title || ''
  if (field === 'date') value = data.date || data.suggested_document_date || ''
  if (field === 'correspondent') value = data.correspondent || data.suggested_correspondent || ''
  if (field === 'tags') value = data.tags || data.suggested_tags || []
  if (field === 'note') value = data.summary || ''
  if (value === null || value === undefined || value === '') return
  const label = typeof value === 'string' ? value : JSON.stringify(value)
  const ok = window.confirm(`Apply ${field} to document: ${label}?`)
  if (!ok) return
  try {
    const reloadSuggestions = Boolean(suggestions.value)
    const reloadPages = pageTexts.value.length > 0
    const reloadQuality = Boolean(contentQuality.value)
    await documentStore.applyToDocument(id, { source, field, value })
    await load()
    if (reloadSuggestions) {
      await loadSuggestions()
    }
    if (reloadPages) {
      await loadPageTexts()
    }
    if (reloadQuality) {
      await loadContentQuality()
    }
  } catch (err: any) {
    suggestionsError.value = err?.message ?? 'Failed to apply suggestion to document'
  }
}

const rows = computed(() => {
  if (!document.value) return []
  const notes = (document.value.notes || []).map((n) => n.note).join(' ')
  const tagNames = (document.value.tags || [])
    .map((tagId) => tags.value.find((t) => t.id === tagId)?.name ?? tagId)
    .join(', ')
  const correspondentName =
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent
  const docTypeName =
    document.value.document_type_name ??
    docTypes.value.find((d) => d.id === document.value?.document_type)?.name ??
    document.value.document_type
  return [
    { label: 'ID', value: document.value.id },
    { label: 'Title', value: document.value.title },
    { label: 'Document date', value: formatDate(document.value.document_date) },
    { label: 'Created', value: formatDateTime(document.value.created) },
    { label: 'Modified', value: formatDateTime(document.value.modified) },
    { label: 'Correspondent', value: correspondentName },
    { label: 'Document type', value: docTypeName },
    { label: 'Tags', value: tagNames },
    { label: 'Original filename', value: document.value.original_file_name },
    { label: 'Notes', value: notes },
  ]
})

const syncPdfFromQuery = () => {
  const pageValue = Number(route.query.page)
  if (Number.isFinite(pageValue) && pageValue > 0) {
    pdfPage.value = pageValue
  }
  const bbox = parseBBox(route.query.bbox)
  pdfHighlights.value = bbox ? [bbox] : []
}

const onPdfPageChange = (value: number) => {
  pdfPage.value = value
  const nextQuery: Record<string, string> = {}
  Object.entries(route.query).forEach(([key, val]) => {
    if (val === undefined || val === null) return
    const entry = Array.isArray(val) ? val[0] : val
    if (typeof entry === 'string') {
      nextQuery[key] = entry
    }
  })
  nextQuery.page = String(value)
  delete nextQuery.bbox
  router.replace({ query: nextQuery })
  pdfHighlights.value = []
}

const formatDate = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language).format(parsed)
}

const formatDateTime = (value?: string | null) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

const load = async () => {
  await documentStore.loadDocument(id)
}

const resync = async () => {
  await documentStore.resync(id, doReembed.value)
}

const loadMeta = async () => {
  await documentStore.loadMeta()
}

const loadPageTexts = async (priority = false) => {
  await documentStore.loadPageTexts(id, priority)
  expandedPages.value = new Set(pageTexts.value.map(pageKey))
}

const loadContentQuality = async (priority = false) => {
  await documentStore.loadContentQuality(id, priority)
}

const loadSuggestions = async () => {
  await documentStore.loadSuggestions(id)
}

const refreshSuggestions = async (source: 'paperless_ocr' | 'vision_ocr') => {
  await documentStore.refreshSuggestions(id, source)
}

const runReprocess = async () => {
  processing.value = true
  try {
    if (doResync.value) {
      await resync()
      await queueStore.refreshStatus()
      if (queueStore.status.enabled) {
        toastStore.push(`Document ${id} queued for processing.`, 'info', 'Queued')
      }
    }
    if (doQuality.value) {
      await loadContentQuality(true)
    }
    if (doPages.value) {
      await loadPageTexts(true)
    }
    if (doSuggestions.value) {
      await loadSuggestions()
    }
  } finally {
    processing.value = false
  }
}

const pageKey = (page: PageText) => `${page.page}:${page.source}`
const isExpanded = (page: PageText) => expandedPages.value.has(pageKey(page))
const togglePage = (page: PageText) => {
  const key = pageKey(page)
  if (expandedPages.value.has(key)) {
    expandedPages.value.delete(key)
  } else {
    expandedPages.value.add(key)
  }
}

onMounted(async () => {
  syncPdfFromQuery()
  await load()
  await loadMeta()
  if (doQuality.value) {
    await loadContentQuality()
  }
  if (doPages.value) {
    await loadPageTexts()
  }
  if (doSuggestions.value) {
    await loadSuggestions()
  }
})

watch(
  () => route.query,
  () => {
    syncPdfFromQuery()
  },
)

watch(doPages, async (value) => {
  if (value && pageTexts.value.length === 0) {
    await loadPageTexts()
  }
})
</script>
