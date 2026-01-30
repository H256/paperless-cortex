<template>
  <section>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-2xl font-semibold tracking-tight text-slate-900">
          {{ document?.title || `Document ${id}` }}
        </h2>
        <p class="text-sm text-slate-500">Document ID: {{ id }}</p>
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

    <section class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
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
    <div v-else class="mt-6 space-y-6">
      <section class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Metadata</div>
        <dl class="mt-3 grid gap-3 md:grid-cols-3">
          <div v-for="row in rows" :key="row.label" class="rounded-lg border border-slate-200 bg-slate-50 p-2">
            <dt class="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{{ row.label }}</dt>
            <dd class="mt-1 text-sm text-slate-900 break-words">
              <template v-if="row.label === 'Notes'">
                <details class="group">
                  <summary class="cursor-pointer text-xs font-semibold text-slate-500">Show notes</summary>
                  <div v-if="row.value" class="mt-2 whitespace-pre-wrap text-sm text-slate-900">
                    {{ row.value }}
                  </div>
                  <div v-else class="mt-2 text-xs text-slate-400">No notes</div>
                </details>
              </template>
              <template v-else>
                <span v-if="row.value !== null && row.value !== undefined && row.value !== ''">{{ row.value }}</span>
                <span v-else class="text-xs text-slate-400">—</span>
              </template>
            </dd>
          </div>
        </dl>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900">Text layer</h3>
          <span class="text-xs font-semibold text-slate-500">Baseline OCR</span>
        </div>
        <textarea
          class="mt-4 w-full min-h-[260px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900"
          readonly
          :value="document?.content || ''"
        ></textarea>

        <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div class="text-sm font-semibold text-slate-700">Text quality (baseline)</div>
          <div v-if="contentQualityError" class="mt-2 text-sm text-rose-600">
            {{ contentQualityError }}
          </div>
          <div v-else-if="!contentQuality" class="mt-2 text-sm text-slate-500">
            No quality metrics loaded.
          </div>
          <div v-else class="mt-3 text-xs text-slate-600">
            <div class="font-semibold text-slate-700">Quality score: {{ contentQuality.score }}</div>
            <div v-if="contentQuality.reasons?.length" class="mt-1">
              Reasons: {{ contentQuality.reasons.join(', ') }}
            </div>
            <div class="mt-3 grid gap-2 md:grid-cols-3">
              <div
                v-for="(value, key) in contentQuality.metrics"
                :key="key"
                class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600"
              >
                {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900">AI suggestions</h3>
          <span class="text-xs text-slate-500">Paperless OCR ? Vision OCR ? Best pick</span>
        </div>
        <div v-if="suggestionsError" class="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {{ suggestionsError }}
        </div>
        <div v-else-if="!suggestions" class="mt-3 text-sm text-slate-500">
          No suggestions loaded.
        </div>
        <div v-else class="mt-4 space-y-4">
          <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div class="flex items-center justify-between">
              <strong class="text-sm text-slate-900">Best pick</strong>
            </div>
            <div v-if="!bestPickSuggestion" class="mt-3 text-sm text-slate-500"><em>No data.</em></div>
            <div v-else class="mt-3 space-y-3">
              <div v-if="bestPickSuggestion.raw">
                <div class="text-xs font-semibold text-slate-500">Raw output</div>
                <pre class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600">{{ bestPickSuggestion.raw }}</pre>
              </div>
              <div v-if="bestPickSuggestion.data" class="space-y-2">
                <div class="flex items-center justify-between text-xs text-slate-500">
                  <span>Summary</span>
                  <button
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                    @click="applyToDocument('best_pick', 'note', bestPickSuggestion.data)"
                  >
                    Save note
                  </button>
                </div>
                <div class="text-sm text-slate-900">{{ bestPickSuggestion.data.summary }}</div>
                <div class="grid gap-2">
                  <div class="flex items-center justify-between text-xs text-slate-500">
                    <span>Document type</span>
                    <span class="text-slate-900">{{ bestPickSuggestion.data.documentType }}</span>
                  </div>
                  <div class="flex items-center justify-between text-xs text-slate-500">
                    <span>Language</span>
                    <span class="text-slate-900">{{ bestPickSuggestion.data.language }}</span>
                  </div>
                </div>
                <div v-for="field in suggestionFields" :key="`best-${field.key}`" class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]">
                  <span class="text-xs text-slate-500">{{ field.label }}</span>
                  <div class="text-sm text-slate-900">
                    <template v-if="field.key === 'tags'">
                      <div v-if="normalizedTags(bestPickSuggestion.data).length" class="flex flex-wrap gap-1.5">
                        <span
                          v-for="tag in normalizedTags(bestPickSuggestion.data)"
                          :key="`best-tag-${tag}`"
                          class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-600"
                        >
                          {{ tag }}
                        </span>
                      </div>
                      <span v-else class="text-xs text-slate-400">No tags suggested</span>
                    </template>
                    <template v-else>
                      {{ fieldValue(bestPickSuggestion.data, field.key) }}
                    </template>
                  </div>
                  <button
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                    @click="applyToDocument('best_pick', field.key, bestPickSuggestion.data)"
                  >
                    Save
                  </button>
                </div>
                <div
                  v-if="(bestPickSuggestion.data.suggested_tags_existing || []).length || (bestPickSuggestion.data.suggested_tags_new || []).length"
                  class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600"
                >
                  <div>Existing tags: {{ (bestPickSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                  <div>New tags: {{ (bestPickSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div class="flex items-center justify-between">
                <strong class="text-sm text-slate-900">Paperless OCR</strong>
                <button
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                  :disabled="suggestionsLoading"
                  @click="refreshSuggestions('paperless_ocr')"
                >
                  Refresh
                </button>
              </div>
              <div v-if="!paperlessSuggestion" class="mt-3 text-sm text-slate-500"><em>No data.</em></div>
              <div v-else class="mt-3 space-y-3">
                <div v-if="paperlessSuggestion.raw">
                  <div class="text-xs font-semibold text-slate-500">Raw output</div>
                  <pre class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600">{{ paperlessSuggestion.raw }}</pre>
                </div>
                <div v-if="paperlessSuggestion.data" class="space-y-2">
                  <div class="text-xs text-slate-500">Summary</div>
                  <div class="text-sm text-slate-900">{{ paperlessSuggestion.data.summary }}</div>
                  <div class="grid gap-2">
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Document type</span>
                      <span class="text-slate-900">{{ paperlessSuggestion.data.documentType || paperlessSuggestion.data.suggested_document_type }}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Language</span>
                      <span class="text-slate-900">{{ paperlessSuggestion.data.language }}</span>
                    </div>
                  </div>
                  <div v-for="field in suggestionFields" :key="`paperless-${field.key}`" class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]">
                    <span class="text-xs text-slate-500">{{ field.label }}</span>
                    <div class="text-sm text-slate-900">
                      <template v-if="field.key === 'tags'">
                        <div v-if="normalizedTags(paperlessSuggestion.data).length" class="flex flex-wrap gap-1.5">
                          <span
                            v-for="tag in normalizedTags(paperlessSuggestion.data)"
                            :key="`paperless-tag-${tag}`"
                            class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-600"
                          >
                            {{ tag }}
                          </span>
                        </div>
                        <span v-else class="text-xs text-slate-400">No tags suggested</span>
                      </template>
                      <template v-else>
                        {{ fieldValue(paperlessSuggestion.data, field.key) }}
                      </template>
                    </div>
                    <div class="flex items-center gap-2">
                      <button
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                        :disabled="suggestionVariantLoading[`paperless_ocr:${field.key}`]"
                        @click="suggestField('paperless_ocr', field.key)"
                      >
                        Suggest new
                      </button>
                      <button
                        class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                        @click="applyToDocument('paperless_ocr', field.key, paperlessSuggestion.data)"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div
                    v-if="(paperlessSuggestion.data.suggested_tags_existing || []).length || (paperlessSuggestion.data.suggested_tags_new || []).length"
                    class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600"
                  >
                    <div>Existing tags: {{ (paperlessSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                    <div>New tags: {{ (paperlessSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`paperless-variants-${field.key}`"
                    class="rounded-md border border-dashed border-slate-200 bg-white p-2"
                  >
                    <div v-if="suggestionVariantError[`paperless_ocr:${field.key}`]" class="text-xs text-rose-600">
                      {{ suggestionVariantError[`paperless_ocr:${field.key}`] }}
                    </div>
                    <div v-if="(suggestionVariants[`paperless_ocr:${field.key}`] || []).length">
                      <div class="text-xs font-semibold text-slate-500">Variants for {{ field.label }}</div>
                      <div v-for="variant in suggestionVariants[`paperless_ocr:${field.key}`]" :key="`${field.key}-${variant}`" class="mt-1 flex items-center justify-between gap-2 text-xs">
                        <span class="text-slate-700">{{ Array.isArray(variant) ? variant.join(', ') : variant }}</span>
                        <button
                          class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300"
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

            <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div class="flex items-center justify-between">
                <strong class="text-sm text-slate-900">Vision OCR</strong>
                <button
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                  :disabled="suggestionsLoading"
                  @click="refreshSuggestions('vision_ocr')"
                >
                  Refresh
                </button>
              </div>
              <div v-if="!visionSuggestion" class="mt-3 text-sm text-slate-500"><em>No data.</em></div>
              <div v-else class="mt-3 space-y-3">
                <div v-if="visionSuggestion.raw">
                  <div class="text-xs font-semibold text-slate-500">Raw output</div>
                  <pre class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600">{{ visionSuggestion.raw }}</pre>
                </div>
                <div v-if="visionSuggestion.data" class="space-y-2">
                  <div class="text-xs text-slate-500">Summary</div>
                  <div class="text-sm text-slate-900">{{ visionSuggestion.data.summary }}</div>
                  <div class="grid gap-2">
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Document type</span>
                      <span class="text-slate-900">{{ visionSuggestion.data.documentType || visionSuggestion.data.suggested_document_type }}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-slate-500">
                      <span>Language</span>
                      <span class="text-slate-900">{{ visionSuggestion.data.language }}</span>
                    </div>
                  </div>
                  <div v-for="field in suggestionFields" :key="`vision-${field.key}`" class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]">
                    <span class="text-xs text-slate-500">{{ field.label }}</span>
                    <div class="text-sm text-slate-900">
                      <template v-if="field.key === 'tags'">
                        <div v-if="normalizedTags(visionSuggestion.data).length" class="flex flex-wrap gap-1.5">
                          <span
                            v-for="tag in normalizedTags(visionSuggestion.data)"
                            :key="`vision-tag-${tag}`"
                            class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-600"
                          >
                            {{ tag }}
                          </span>
                        </div>
                        <span v-else class="text-xs text-slate-400">No tags suggested</span>
                      </template>
                      <template v-else>
                        {{ fieldValue(visionSuggestion.data, field.key) }}
                      </template>
                    </div>
                    <div class="flex items-center gap-2">
                      <button
                        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
                        :disabled="suggestionVariantLoading[`vision_ocr:${field.key}`]"
                        @click="suggestField('vision_ocr', field.key)"
                      >
                        Suggest new
                      </button>
                      <button
                        class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300"
                        @click="applyToDocument('vision_ocr', field.key, visionSuggestion.data)"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div
                    v-if="(visionSuggestion.data.suggested_tags_existing || []).length || (visionSuggestion.data.suggested_tags_new || []).length"
                    class="rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600"
                  >
                    <div>Existing tags: {{ (visionSuggestion.data.suggested_tags_existing || []).join(', ') }}</div>
                    <div>New tags: {{ (visionSuggestion.data.suggested_tags_new || []).join(', ') }}</div>
                  </div>
                  <div
                    v-for="field in suggestionFields"
                    :key="`vision-variants-${field.key}`"
                    class="rounded-md border border-dashed border-slate-200 bg-white p-2"
                  >
                    <div v-if="suggestionVariantError[`vision_ocr:${field.key}`]" class="text-xs text-rose-600">
                      {{ suggestionVariantError[`vision_ocr:${field.key}`] }}
                    </div>
                    <div v-if="(suggestionVariants[`vision_ocr:${field.key}`] || []).length">
                      <div class="text-xs font-semibold text-slate-500">Variants for {{ field.label }}</div>
                      <div v-for="variant in suggestionVariants[`vision_ocr:${field.key}`]" :key="`${field.key}-${variant}`" class="mt-1 flex items-center justify-between gap-2 text-xs">
                        <span class="text-slate-700">{{ Array.isArray(variant) ? variant.join(', ') : variant }}</span>
                        <button
                          class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300"
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

      <section class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-slate-900">Extracted page texts (debug)</h3>
          <span class="text-xs text-slate-500">Page-wise OCR</span>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" v-model="showPreviews" />
            Show previews
          </label>
          <label class="inline-flex items-center gap-2">
            <span>Preview size</span>
            <input
              type="range"
              min="512"
              max="1600"
              step="64"
              v-model.number="previewMaxDim"
              :disabled="!showPreviews"
            />
            <span class="tabular-nums">{{ previewMaxDim }}px</span>
          </label>
        </div>
        <div class="mt-4">
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Aggregated text context</div>
          <textarea
            class="mt-2 w-full min-h-[180px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900"
            readonly
            :value="aggregatedText"
          ></textarea>
        </div>
        <div v-if="pageTextsError" class="mt-3 text-sm text-rose-600">{{ pageTextsError }}</div>
        <div v-else-if="pageTexts.length === 0" class="mt-3 text-sm text-slate-500">
          No extracted page text loaded.
        </div>
        <div v-else class="mt-4 space-y-4">
          <div v-for="page in pageTexts" :key="page.page" class="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div class="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span>Page {{ page.page }} · Source: {{ page.source }}</span>
              <button
                class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300"
                @click="togglePage(page)"
              >
                {{ isExpanded(page) ? 'Hide' : 'Show' }}
              </button>
            </div>
            <div v-if="isExpanded(page)">
            <div v-if="page.quality" class="mt-2 text-xs text-slate-600">
              <div class="font-semibold text-slate-700">Quality score: {{ page.quality.score }}</div>
              <div v-if="page.quality.reasons?.length" class="mt-1">Reasons: {{ page.quality.reasons.join(', ') }}</div>
              <div class="mt-3 grid gap-2 md:grid-cols-3">
                <div
                  v-for="(value, key) in page.quality.metrics"
                  :key="key"
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600"
                >
                  {{ key }}: {{ value.toFixed ? value.toFixed(3) : value }}
                </div>
              </div>
            </div>
            <div class="mt-3 grid gap-3 lg:grid-cols-[minmax(0,360px)_1fr]">
              <div v-if="shouldShowPreview(page)" class="rounded-lg border border-slate-200 bg-white p-2">
                <div class="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Preview</div>
                <div class="relative mt-2">
                  <div
                    v-if="previewStatus[previewKey(page)]?.loading"
                    class="absolute inset-0 flex items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50 text-[11px] text-slate-400"
                  >
                    Loading preview…
                  </div>
                  <div
                    v-else-if="previewStatus[previewKey(page)]?.error"
                    class="absolute inset-0 flex items-center justify-center rounded-md border border-rose-200 bg-rose-50 text-[11px] text-rose-600"
                  >
                    {{ previewStatus[previewKey(page)]?.error }}
                  </div>
                  <img
                    class="w-full rounded-md border border-slate-200"
                    :class="previewStatus[previewKey(page)]?.error ? 'opacity-20' : ''"
                    :src="pagePreviewUrl(page)"
                    loading="lazy"
                    :alt="`Page ${page.page} preview`"
                    @load="onPreviewLoad(page)"
                    @error="onPreviewError(page)"
                  />
                </div>
              </div>
              <textarea
                class="w-full min-h-[140px] rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-900"
                readonly
                :value="page.text"
              ></textarea>
            </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>


<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { ExternalLink, RefreshCcw, RefreshCw } from 'lucide-vue-next';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import IconButton from '../components/IconButton.vue';
import { useDocumentDetailStore } from '../stores/documentDetailStore';
import { useStatusStore } from '../stores/statusStore';
import { PageText } from '../services/documents';

const route = useRoute();
const id = Number(route.params.id);

const documentStore = useDocumentDetailStore();
const statusStore = useStatusStore();
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
} = storeToRefs(documentStore);

const processing = ref(false);
const doResync = ref(true);
const doReembed = ref(true);
const doQuality = ref(true);
const doPages = ref(true);
const doSuggestions = ref(true);
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api';
const previewMaxDimStorageKey = 'paperless_preview_max_dim';
const previewToggleStorageKey = 'paperless_preview_show';
const storedPreviewMaxDim = Number(window.localStorage?.getItem(previewMaxDimStorageKey) || 1024);
const storedShowPreviews = window.localStorage?.getItem(previewToggleStorageKey);
const showPreviews = ref(storedShowPreviews !== '0');
const previewMaxDim = ref(Number.isFinite(storedPreviewMaxDim) ? storedPreviewMaxDim : 1024);
const expandedPages = ref<Set<string>>(new Set());
const previewStatus = ref<Record<string, { loading: boolean; error: string }>>({});

const paperlessBaseUrl = computed(() => import.meta.env.VITE_PAPERLESS_BASE_URL || statusStore.paperlessBaseUrl || '');
const paperlessUrl = computed(() =>
  paperlessBaseUrl.value && document.value
    ? `${paperlessBaseUrl.value.replace(/\/$/, '')}/documents/${document.value.id}`
    : ''
);

const normalizeSuggestion = (input: any) => {
  if (!input || (typeof input === 'object' && Object.keys(input).length === 0)) {
    return null;
  }
  const raw = input.raw || null;
  const data = input.parsed || (raw ? null : input);
  return { raw, data };
};

const paperlessSuggestion = computed(() => normalizeSuggestion(suggestions.value?.paperless_ocr));
const visionSuggestion = computed(() => normalizeSuggestion(suggestions.value?.vision_ocr));
const bestPickSuggestion = computed(() => normalizeSuggestion(suggestions.value?.best_pick));
const suggestionFields = [
  { key: 'title', label: 'Suggested title' },
  { key: 'date', label: 'Suggested date' },
  { key: 'correspondent', label: 'Suggested correspondent' },
  { key: 'tags', label: 'Suggested tags' },
];

const aggregatedText = computed(() => {
  if (!pageTexts.value.length) return document.value?.content || '';
  return pageTexts.value.map((page) => page.text).join('\n\n');
});

const fieldValue = (data: any, field: string) => {
  if (!data) return '';
  if (field === 'title') return data.title || data.suggested_title;
  if (field === 'date') return data.date || data.suggested_document_date;
  if (field === 'correspondent') return data.correspondent || data.suggested_correspondent;
  if (field === 'tags') return data.tags || data.suggested_tags;
  return data[field];
};

const normalizedTags = (data: any): string[] => {
  const raw = fieldValue(data, 'tags');
  if (!raw) return [];
  if (Array.isArray(raw)) return raw.map((tag) => String(tag)).filter(Boolean);
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (Array.isArray(parsed)) {
          return parsed.map((tag) => String(tag)).filter(Boolean);
        }
      } catch {
        // fall through to splitting
      }
    }
    return trimmed
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return [String(raw)];
};

const suggestField = async (source: 'paperless_ocr' | 'vision_ocr', field: string) => {
  await documentStore.suggestField(id, source, field);
};

const applyVariant = async (source: 'paperless_ocr' | 'vision_ocr', field: string, value: any) => {
  const label = typeof value === 'string' ? value : JSON.stringify(value);
  const ok = window.confirm(`Overwrite ${field} with: ${label}?`);
  if (!ok) return;
  await documentStore.applyVariant(id, source, field, value);
};

const applyToDocument = async (source: string, field: string, data: any) => {
  if (!data) return;
  let value: any = data[field];
  if (field === 'title') value = data.title || data.suggested_title || '';
  if (field === 'date') value = data.date || data.suggested_document_date || '';
  if (field === 'correspondent') value = data.correspondent || data.suggested_correspondent || '';
  if (field === 'tags') value = data.tags || data.suggested_tags || [];
  if (field === 'note') value = data.summary || '';
  if (value === null || value === undefined || value === '') return;
  const label = typeof value === 'string' ? value : JSON.stringify(value);
  const ok = window.confirm(`Apply ${field} to document: ${label}?`);
  if (!ok) return;
  try {
    await documentStore.applyToDocument(id, { source, field, value });
    await load();
  } catch (err: any) {
    suggestionsError.value = err?.message ?? 'Failed to apply suggestion to document';
  }
};

const rows = computed(() => {
  if (!document.value) return [];
  const notes = (document.value.notes || []).map((n) => n.note).join(' ');
  const tagNames = (document.value.tags || [])
    .map((tagId) => tags.value.find((t) => t.id === tagId)?.name ?? tagId)
    .join(', ');
  const correspondentName =
    document.value.correspondent_name ??
    correspondents.value.find((c) => c.id === document.value?.correspondent)?.name ??
    document.value.correspondent;
  const docTypeName =
    document.value.document_type_name ??
    docTypes.value.find((d) => d.id === document.value?.document_type)?.name ??
    document.value.document_type;
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
  ];
});

const formatDate = (value?: string | null) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(navigator.language).format(parsed);
};

const formatDateTime = (value?: string | null) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(navigator.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
};

const load = async () => {
  await documentStore.loadDocument(id);
};

const resync = async () => {
  await documentStore.resync(id, doReembed.value);
};

const loadMeta = async () => {
  await documentStore.loadMeta();
};

const loadPageTexts = async (priority = false) => {
  await documentStore.loadPageTexts(id, priority);
  expandedPages.value = new Set(pageTexts.value.map(pageKey));
  previewStatus.value = {};
  if (showPreviews.value) {
    pageTexts.value.filter((page) => page.source === 'vision_ocr').forEach(markPreviewLoading);
  }
};

const loadContentQuality = async (priority = false) => {
  await documentStore.loadContentQuality(id, priority);
};

const loadSuggestions = async () => {
  await documentStore.loadSuggestions(id);
};

const refreshSuggestions = async (source: 'paperless_ocr' | 'vision_ocr') => {
  await documentStore.refreshSuggestions(id, source);
};

const runReprocess = async () => {
  processing.value = true;
  try {
    if (doResync.value) {
      await resync();
    }
    if (doQuality.value) {
      await loadContentQuality(true);
    }
    if (doPages.value) {
      await loadPageTexts(true);
    }
    if (doSuggestions.value) {
      await loadSuggestions();
    }
  } finally {
    processing.value = false;
  }
};

const previewKey = (page: PageText) => `preview:${page.page}:${page.source}`;
const markPreviewLoading = (page: PageText) => {
  previewStatus.value = {
    ...previewStatus.value,
    [previewKey(page)]: { loading: true, error: '' },
  };
};
const onPreviewLoad = (page: PageText) => {
  previewStatus.value = {
    ...previewStatus.value,
    [previewKey(page)]: { loading: false, error: '' },
  };
};
const onPreviewError = (page: PageText) => {
  previewStatus.value = {
    ...previewStatus.value,
    [previewKey(page)]: { loading: false, error: 'Preview unavailable' },
  };
};

const pageKey = (page: PageText) => `${page.page}:${page.source}`;
const isExpanded = (page: PageText) => expandedPages.value.has(pageKey(page));
const togglePage = (page: PageText) => {
  const key = pageKey(page);
  if (expandedPages.value.has(key)) {
    expandedPages.value.delete(key);
  } else {
    expandedPages.value.add(key);
    if (showPreviews.value && page.source === 'vision_ocr') {
      markPreviewLoading(page);
    }
  }
};

const shouldShowPreview = (page: PageText) => {
  return showPreviews.value && isExpanded(page) && page.source === 'vision_ocr';
};

const pagePreviewUrl = (page: PageText) => {
  const url = `${apiBaseUrl}/documents/${id}/page-preview?page=${page.page}&max_dim=${previewMaxDim.value}`;
  return url;
};

onMounted(async () => {
  await load();
  await loadMeta();
  if (doQuality.value) {
    await loadContentQuality();
  }
  if (doPages.value) {
    await loadPageTexts();
  }
  if (doSuggestions.value) {
    await loadSuggestions();
  }
});

watch(doPages, async (value) => {
  if (value && pageTexts.value.length === 0) {
    await loadPageTexts();
  }
});

watch(previewMaxDim, (value) => {
  window.localStorage.setItem(previewMaxDimStorageKey, String(value));
  if (showPreviews.value) {
    pageTexts.value
      .filter((page) => page.source === 'vision_ocr' && isExpanded(page))
      .forEach(markPreviewLoading);
  }
});

watch(showPreviews, (value) => {
  window.localStorage.setItem(previewToggleStorageKey, value ? '1' : '0');
  if (value) {
    pageTexts.value
      .filter((page) => page.source === 'vision_ocr' && isExpanded(page))
      .forEach(markPreviewLoading);
  }
});
</script>
