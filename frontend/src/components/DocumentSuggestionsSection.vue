<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">AI suggestions</h3>
      <span class="text-xs text-slate-500 dark:text-slate-400"
        >Paperless OCR · Vision OCR</span
      >
    </div>

    <div class="mt-3 flex flex-wrap items-center gap-2">
      <span class="text-xs font-semibold text-slate-500 dark:text-slate-400">Presets</span>
      <button
        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
        :disabled="suggestionsLoading"
        data-testid="preset-no-correspondent"
        @click="applyPresetNoCorrespondent"
      >
        No correspondent
      </button>
      <button
        class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
        :disabled="suggestionsLoading || !importDateOnly(importDate)"
        :title="
          importDateOnly(importDate)
            ? `Set issue date to the import date (${importDateOnly(importDate)})`
            : 'No import date available'
        "
        data-testid="preset-issue-date-import"
        @click="applyPresetIssueDateImport"
      >
        Issue date = import date
      </button>
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
        v-if="hasTextCandidates"
        class="rounded-xl border border-sky-200 bg-sky-50 p-4 dark:border-sky-900/50 dark:bg-sky-950/30"
        data-testid="text-candidates"
      >
        <div class="flex items-center justify-between">
          <strong class="text-sm text-slate-900 dark:text-slate-100">Candidates from text</strong>
          <span class="text-xs text-slate-500 dark:text-slate-400"
            >Found in the document text, no AI involved</span
          >
        </div>
        <div v-if="dateCandidates.length" class="mt-3">
          <div class="text-xs font-semibold text-slate-500 dark:text-slate-400">Date</div>
          <div class="mt-1.5 flex flex-wrap gap-2">
            <button
              v-for="candidate in dateCandidates"
              :key="`date-${candidate.value}`"
              type="button"
              class="rounded-lg border px-2.5 py-1 text-left text-xs"
              :class="candidateClass(isCandidateSelected('date', candidate.value))"
              :title="candidateTitle(candidate)"
              :data-testid="`candidate-date-${candidate.value}`"
              :disabled="suggestionsLoading || applying"
              @click="toggleCandidate('date', candidate.value)"
            >
              <span class="font-semibold">{{ formatCandidateDate(candidate.value) }}</span>
              <span class="ml-1.5 text-slate-500 dark:text-slate-400">{{
                candidateLabel(candidate.label)
              }}</span>
              <span
                v-if="(candidate.occurrences ?? 1) > 1"
                class="ml-1 text-slate-400 dark:text-slate-500"
                >{{ candidate.occurrences }}×</span
              >
              <button
                v-if="candidate.page"
                type="button"
                class="ml-1.5 rounded border border-sky-200 bg-white px-1 py-0.5 text-[10px] font-semibold text-sky-600 hover:border-sky-300 dark:border-sky-900/50 dark:bg-slate-900 dark:text-sky-300"
                :data-testid="`jump-page-candidate-date-${candidate.value}`"
                title="Jump to the PDF page where this date was found"
                @click.stop="jumpToPage(candidate.page)"
              >
                p.{{ candidate.page }}
              </button>
            </button>
          </div>
        </div>
        <div v-if="correspondentCandidates.length" class="mt-3">
          <div class="text-xs font-semibold text-slate-500 dark:text-slate-400">Correspondent</div>
          <div class="mt-1.5 flex flex-wrap gap-2">
            <button
              v-for="candidate in correspondentCandidates"
              :key="`corr-${candidate.name}`"
              type="button"
              class="rounded-lg border px-2.5 py-1 text-left text-xs"
              :class="candidateClass(isCandidateSelected('correspondent', candidate.name))"
              :title="candidate.context || candidate.name"
              :data-testid="`candidate-correspondent-${candidate.name}`"
              :disabled="suggestionsLoading || applying"
              @click="toggleCandidate('correspondent', candidate.name)"
            >
              <span class="font-semibold">{{ candidate.name }}</span>
              <span
                class="ml-1.5"
                :class="
                  candidate.known
                    ? 'text-emerald-600 dark:text-emerald-300'
                    : 'text-amber-600 dark:text-amber-300'
                "
                >{{ candidate.known ? 'known' : 'new' }}</span
              >
            </button>
          </div>
        </div>
      </div>
      <details
        class="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
        data-testid="suggest-guidance"
        :open="guidanceActive"
      >
        <summary class="cursor-pointer text-sm font-semibold text-slate-900 dark:text-slate-100">
          Guidance for "Suggest new"
          <span v-if="guidanceActive" class="ml-2 text-xs font-normal text-emerald-600 dark:text-emerald-300"
            >active</span
          >
        </summary>
        <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">
          The model only sees the text, not the page layout. Mark the passage that contains the
          answer, or add a short instruction. It is sent with every "Suggest new" request below.
        </p>
        <label class="mt-3 block text-xs font-semibold text-slate-600 dark:text-slate-300">
          Hint (optional)
          <input
            v-model="hint"
            type="text"
            maxlength="300"
            class="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm font-normal text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder="e.g. invoice date, not the delivery date"
            data-testid="guidance-hint"
          />
        </label>
        <label
          v-if="textSources.length > 1"
          class="mt-3 block text-xs font-semibold text-slate-600 dark:text-slate-300"
        >
          Text the model reads
          <select
            v-model="modelTextSource"
            class="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm font-normal text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            data-testid="guidance-model-text"
          >
            <option value="">Each panel's own text (default)</option>
            <option v-for="source in modelTextOptions" :key="source.key" :value="source.key">
              {{ source.label }}
            </option>
          </select>
        </label>
        <label class="mt-3 block text-xs font-semibold text-slate-600 dark:text-slate-300">
          Only these pages (optional)
          <input
            v-model="pagesInput"
            type="text"
            maxlength="100"
            class="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm font-normal text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder="e.g. 1 or 1-2,4"
            data-testid="guidance-pages"
          />
          <span
            v-if="pagesInvalid"
            class="mt-1 block font-normal text-rose-600 dark:text-rose-300"
            data-testid="guidance-pages-invalid"
            >Use page numbers like 1 or 1-2,4.</span
          >
        </label>
        <div class="mt-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs font-semibold text-slate-600 dark:text-slate-300">Document text</span>
            <select
              v-if="textSources.length > 1"
              v-model="activeTextSource"
              class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-900"
              data-testid="guidance-source"
            >
              <option v-for="source in textSources" :key="source.key" :value="source.key">
                {{ source.label }}
              </option>
            </select>
            <button
              type="button"
              class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
              data-testid="guidance-use-selection"
              @click="useSelectionAsFocus"
            >
              Use selected text as focus
            </button>
          </div>
          <pre
            ref="guidanceTextRef"
            class="mt-2 max-h-48 select-text overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            data-testid="guidance-text"
            >{{ activeTextSourceText || 'No document text available.' }}</pre
          >
          <div v-if="guidanceNotice" class="mt-1 text-xs text-amber-600 dark:text-amber-300">
            {{ guidanceNotice }}
          </div>
        </div>
        <div
          v-if="focusText"
          class="mt-3 flex items-start justify-between gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-2 text-xs dark:border-emerald-900/50 dark:bg-emerald-950/30"
          data-testid="guidance-focus"
        >
          <span class="min-w-0 break-words text-slate-800 dark:text-slate-100"
            ><span class="font-semibold">Focus:</span> {{ focusPreview }}</span
          >
          <button
            type="button"
            class="shrink-0 rounded border border-slate-200 bg-white px-1.5 py-0.5 font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            data-testid="guidance-clear-focus"
            @click="focusText = ''"
          >
            Clear
          </button>
        </div>
      </details>

      <div
        class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700"
        data-testid="suggestion-comparison-table"
      >
        <table class="w-full min-w-[760px] border-collapse text-left text-sm">
          <thead>
            <tr class="border-b border-slate-200 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
              <th class="px-3 py-2 font-semibold">Field</th>
              <th class="px-3 py-2 font-semibold">Current</th>
              <th v-for="column in columns" :key="`head-${column.key}`" class="px-3 py-2 font-semibold">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <span>{{ column.label }}</span>
                  <span v-if="column.allowActions" class="flex items-center gap-2">
                    <button
                      class="rounded-md border border-slate-200 bg-white px-2 py-0.5 font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                      :disabled="suggestionsLoading || isVariantBusy(column.source)"
                      @click="emit('refresh', column.source)"
                    >
                      <span v-if="suggestionsLoading" class="inline-flex items-center gap-2">
                        <Loader2 class="h-3.5 w-3.5 animate-spin" />
                        Refreshing...
                      </span>
                      <span v-else>Refresh</span>
                    </button>
                    <button
                      class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700 hover:border-emerald-300 disabled:opacity-60 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                      :disabled="suggestionsLoading || isVariantBusy(column.source)"
                      title="Generate alternative values for all suggestion fields."
                      @click="generateAllVariants(column.source)"
                    >
                      <span v-if="isVariantBusy(column.source)" class="inline-flex items-center gap-2">
                        <Loader2 class="h-3.5 w-3.5 animate-spin" />
                        Generating...
                      </span>
                      <span v-else>Generate variants</span>
                    </button>
                  </span>
                </div>
                <div v-if="suggestionMetaLine(column.source)" class="mt-1 text-[11px] font-normal">
                  {{ suggestionMetaLine(column.source) }}
                </div>
                <div
                  v-if="warningsFor(column.source).length"
                  class="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
                >
                  <div class="font-semibold">Check these suggested values</div>
                  <ul class="mt-1 list-disc space-y-0.5 pl-4">
                    <li v-for="(warning, index) in warningsFor(column.source)" :key="index">{{ warning }}</li>
                  </ul>
                </div>
                <div v-if="column.suggestion?.raw" class="mt-1">
                  <div class="text-[11px] font-semibold">Raw output</div>
                  <pre class="max-h-32 overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-2 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">{{ column.suggestion.raw }}</pre>
                </div>
              </th>
              <th class="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="field in tableFields"
              :key="`row-${field.key}`"
              class="border-b border-slate-200 last:border-b-0 dark:border-slate-700"
            >
              <td class="px-3 py-2 align-top">
                <label
                  v-if="field.checkbox"
                  class="flex cursor-pointer items-start gap-2 text-xs text-slate-500 dark:text-slate-400"
                >
                  <input
                    type="checkbox"
                    class="mt-0.5"
                    :checked="field.checked"
                    :disabled="suggestionsLoading || applying"
                    :data-testid="`select-${field.checkboxSource}-${field.key}`"
                    @change="field.toggle()"
                  />
                  <span>{{ field.label }}</span>
                </label>
                <span v-else class="text-xs text-slate-500 dark:text-slate-400">{{ field.label }}</span>
                <span
                  v-if="field.agreement"
                  class="mt-1 inline-block rounded-full border px-2 py-0.5 text-[11px] font-semibold"
                  :class="
                    field.agreement.startsWith('single')
                      ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200'
                      : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200'
                  "
                  :data-testid="`agreement-${field.key}`"
                >
                  {{ field.agreement }}
                </span>
              </td>
              <td class="px-3 py-2 align-top text-slate-500 dark:text-slate-400">
                <span class="break-words">{{ field.current || '—' }}</span>
              </td>
              <td
                v-for="column in columns"
                :key="`cell-${column.key}-${field.key}`"
                class="px-3 py-2 align-top"
              >
                <div v-if="!column.hasField(field.key)" class="text-xs text-slate-400 dark:text-slate-500">
                  <em>No data.</em>
                </div>
                <template v-else>
                  <template v-if="field.key === 'tags'">
                    <div v-if="column.tagsFor(field.key).length" class="flex flex-wrap gap-1.5">
                      <component
                        :is="column.allowActions ? 'button' : 'span'"
                        v-for="tag in column.tagsFor(field.key)"
                        :key="`tag-${column.key}-${field.key}-${tag}`"
                        :type="column.allowActions ? 'button' : undefined"
                        class="rounded-full border px-2 py-0.5 text-xs font-semibold"
                        :class="
                          isTagSelected(column.sourceKey, tag)
                            ? 'border-emerald-400 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200'
                            : 'border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
                        "
                        :title="column.allowActions ? 'Select tag for Apply selected' : undefined"
                        @click="column.allowActions && toggleTag(column.sourceKey, tag)"
                      >
                        {{ tag }}
                      </component>
                    </div>
                    <span v-else class="text-xs text-slate-400 dark:text-slate-500">No tags suggested</span>
                  </template>
                  <template v-else>
                    <span class="break-words text-slate-900 dark:text-slate-100">{{
                      column.valueFor(field.key)
                    }}</span>
                  </template>
                  <div
                    v-if="field.key === 'date' && column.pageFor(field.key)"
                    class="mt-1"
                  >
                    <button
                      class="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                      :data-testid="`jump-page-${column.key}-${field.key}`"
                      @click="jumpToPage(column.pageFor(field.key))"
                    >
                      Jump to page {{ column.pageFor(field.key) }}
                    </button>
                  </div>
                  <div
                    v-if="
                      column.allowActions &&
                      (variantError(column.source, field.key) ||
                        isVariantLoading(column.source, field.key) ||
                        (variantsFor(column.source, field.key) || []).length)
                    "
                    class="mt-2 rounded-md border border-dashed border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900"
                  >
                    <div class="text-xs font-semibold text-slate-500 dark:text-slate-300">
                      Variants for {{ field.label }}
                    </div>
                    <div v-if="variantError(column.source, field.key)" class="mt-2 text-xs text-rose-600">
                      {{ variantError(column.source, field.key) }}
                    </div>
                    <div
                      v-else-if="isVariantLoading(column.source, field.key)"
                      class="mt-2 inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400"
                    >
                      <Loader2 class="h-3.5 w-3.5 animate-spin" />
                      Generating variants...
                    </div>
                    <div
                      v-else
                      v-for="(variant, index) in variantsFor(column.source, field.key)"
                      :key="`${column.key}-${field.key}-${index}-${variant}`"
                      class="mt-2 flex items-center justify-between gap-2 text-xs"
                    >
                      <span class="text-slate-700 dark:text-slate-200">{{
                        Array.isArray(variant) ? variant.join(', ') : variant
                      }}</span>
                      <button
                        class="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-500"
                        :disabled="suggestionsLoading"
                        @click="openVariantDialog(column.source, field.key, variant)"
                      >
                        Use
                      </button>
                    </div>
                  </div>
                </template>
              </td>
              <td class="px-3 py-2 align-top">
                <div class="flex items-start gap-2">
                  <button
                    v-if="field.suggestSource"
                    class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                    :disabled="suggestionsLoading || isVariantLoading(field.suggestSource, field.key)"
                    @click="requestSuggest(field.suggestSource, field.key)"
                  >
                    <span
                      v-if="isVariantLoading(field.suggestSource, field.key)"
                      class="inline-flex items-center gap-2"
                    >
                      <Loader2 class="h-3.5 w-3.5 animate-spin" />
                      {{ waitLabel(field.suggestSource, field.key) }}
                    </span>
                    <span v-else>Suggest new</span>
                  </button>
                  <button
                    v-if="field.saveSource"
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                    :disabled="suggestionsLoading"
                    @click="openApplyDialog(field.saveSource, field.key, field.saveData ?? {})"
                  >
                    Save
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        v-if="selectedItems.length"
        class="sticky bottom-3 z-10 rounded-xl border border-emerald-200 bg-white p-3 shadow-lg dark:border-emerald-900/50 dark:bg-slate-900"
        data-testid="apply-selected-bar"
      >
        <div class="text-xs font-semibold text-slate-500 dark:text-slate-400">
          Selected changes (only these are written to the document)
        </div>
        <ul class="mt-2 space-y-1 text-xs">
          <li
            v-for="item in selectedItems"
            :key="item.field"
            class="grid grid-cols-[110px_1fr] gap-2"
          >
            <span class="text-slate-500 dark:text-slate-400"
              >{{ item.label }} · {{ sourceLabel(item.source) }}</span
            >
            <span class="min-w-0 break-words text-slate-900 dark:text-slate-100">
              <span class="text-slate-400 line-through">{{ item.current || '—' }}</span>
              →
              <span class="font-semibold">{{ item.next }}</span>
            </span>
          </li>
        </ul>
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="rounded-md border border-emerald-300 bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
            :disabled="applying || suggestionsLoading"
            data-testid="apply-selected"
            @click="applySelected"
          >
            {{ applying ? 'Applying...' : `Apply selected (${selectedItems.length})` }}
          </button>
          <button
            type="button"
            class="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            :disabled="applying"
            @click="clearSelection"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  </section>

  <ChoiceDialog
    :open="showVariantDialog"
    title="Use suggestion variant"
    :message="
      variantDialog
        ? `Selected value: ${typeof variantDialog.value === 'string'
            ? variantDialog.value
            : JSON.stringify(variantDialog.value)}`
        : 'Do you want to update the document or only the suggestion value?'
    "
    primary-label="Update document"
    secondary-label="Update suggestion"
    cancel-label="Cancel"
    @primary="confirmVariantUpdateDocument"
    @secondary="confirmVariantUpdateSuggestion"
    @cancel="closeVariantDialog"
  />
  <ConfirmDialog
    :open="showApplyDialog"
    title="Apply suggestion"
    :message="
      applyDialog
        ? `Apply ${applyDialog.field} to document: ${applyDialog.label}?`
        : 'Apply suggestion to document?'
    "
    confirm-label="Apply"
    cancel-label="Cancel"
    @confirm="confirmApplyToDocument"
    @cancel="closeApplyDialog"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import ChoiceDialog from './ChoiceDialog.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import { mergeTagNames, type SuggestionApplyItem } from '../utils/suggestionSelection'
import {
  computeAgreement,
  type AgreementField,
  type AgreementResult,
} from '../utils/suggestionAgreement'
import type { CorrespondentCandidate, DateCandidate } from '../api/generated/model'

type SuggestionPayload = Record<string, unknown>
type SuggestionSource = 'paperless_ocr' | 'vision_ocr' | 'similar_docs'
type SuggestionState = {
  paperless_ocr?: SuggestionPayload
  vision_ocr?: SuggestionPayload
  similar_docs?: SuggestionPayload
  suggestions_meta?: Record<string, unknown>
}

const props = withDefaults(defineProps<{
  suggestions: SuggestionState | null
  suggestionsError: string
  suggestionsLoading: boolean
  suggestionVariants: Record<string, unknown[]>
  suggestionVariantLoading: Record<string, boolean>
  suggestionVariantError: Record<string, string>
  suggestionVariantWait?: Record<string, number>
  currentValues: {
    title: string
    date: string
    correspondent: string
    tags: string
    note: string
  }
  currentTagList?: string[]
  applying?: boolean
  /** Beside the PDF on wide screens: stack the panels and field rows in the narrower column. */
  compact?: boolean
  importDate?: string
  textSources?: Array<{ key: string; label: string; text: string }>
  textCandidates?: {
    dates?: DateCandidate[]
    correspondents?: CorrespondentCandidate[]
  } | null
}>(), {
  currentTagList: () => [],
  applying: false,
  compact: false,
  importDate: '',
  textCandidates: null,
  textSources: () => [],
})

const emit = defineEmits<{
  (e: 'refresh', source: SuggestionSource): void
  (
    e: 'suggestField',
    source: SuggestionSource,
    field: string,
    guidance?: {
      focus_text?: string
      hint?: string
      text_source?: 'paperless_ocr' | 'vision_ocr'
      pages?: string
    },
  ): void
  (e: 'applyVariant', source: SuggestionSource, field: string, value: unknown): void
  (e: 'applyVariantToDocument', source: SuggestionSource, field: string, value: unknown): void
  (e: 'applyToDocument', source: string, field: string, value: unknown): void
  (e: 'applySelected', items: SuggestionApplyItem[]): void
  (e: 'jumpToPage', page: number): void
}>()
const suggestionFields = [
  { key: 'title', label: 'Suggested title' },
  { key: 'date', label: 'Suggested date' },
  { key: 'correspondent', label: 'Suggested correspondent' },
  { key: 'tags', label: 'Suggested tags' },
]

const normalizeSuggestion = (input: unknown) => {
  if (!input || (typeof input === 'object' && Object.keys(input).length === 0)) {
    return null
  }
  const raw = (input as { raw?: string | null }).raw || null
  const parsed = (input as { parsed?: SuggestionPayload }).parsed
  const data = parsed || (raw ? null : (input as SuggestionPayload))
  return { raw, data }
}

const suggestionsMeta = computed(
  () => (props.suggestions as { suggestions_meta?: Record<string, unknown> } | null)?.suggestions_meta || {},
)

const warningsFor = (source: SuggestionSource): string[] => {
  const raw = props.suggestions?.[source]
  if (!raw || typeof raw !== 'object') {
    return []
  }
  const warnings = (raw as { suggestion_warnings?: unknown }).suggestion_warnings
  return Array.isArray(warnings) ? (warnings as string[]) : []
}

const panelFor = (key: 'paperless_ocr' | 'vision_ocr' | 'similar_docs') =>
  normalizeSuggestion(props.suggestions?.[key])

const columnHasField = (
  column: { suggestion: { data?: SuggestionPayload | null } | null },
  field: string,
) =>
  Boolean(column.suggestion?.data && hasSuggestedValue(column.suggestion.data, field))

const columnValueFor = (
  column: { suggestion: { data?: SuggestionPayload | null } | null },
  field: string,
) =>
  fieldValue(column.suggestion?.data ?? {}, field)

const columnTagsFor = (
  column: { suggestion: { data?: SuggestionPayload | null } | null },
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  field: string,
) =>
  normalizedTags(column.suggestion?.data ?? {})

const columnPageFor = (
  column: { suggestion: { data?: SuggestionPayload | null } | null },
  field: string,
) => {
  const page = column.suggestion?.data?.[field === 'date' ? 'page' : field]
  return typeof page === 'number' && page > 0 ? page : 0
}

const normalizeComparable = (value: unknown): string => {
  if (value == null) return ''
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).sort().join(',')
  return String(value).trim()
}

const columns = computed(() =>
  ([
    { key: 'vision_ocr', label: 'Vision OCR', source: 'vision_ocr' as const, allowActions: true },
    { key: 'paperless_ocr', label: 'Paperless OCR', source: 'paperless_ocr' as const, allowActions: true },
    { key: 'similar_docs', label: 'Similar docs', source: 'similar_docs' as const, allowActions: false },
  ] as const).map((column) => {
    const base = panelFor(column.key)
    return {
      ...column,
      sourceKey: column.key,
      suggestion: base,
      hasField: (field: string) => columnHasField({ suggestion: base }, field),
      valueFor: (field: string) => columnValueFor({ suggestion: base }, field),
      tagsFor: (field: string) => columnTagsFor({ suggestion: base }, field),
      pageFor: (field: string) => columnPageFor({ suggestion: base }, field),
    }
  }),
)

const tableFields = computed(() => {
  const cols = columns.value
  const makeRow = (key: string, label: string, options: { current: string }) => {
    const present = cols.filter((column) => columnHasField({ suggestion: column.suggestion }, key))
    const values = present.map((column) => normalizeComparable(column.valueFor(key)))
    const distinct = new Set(values)
    let agreement = ''
    if (present.length >= 2 && distinct.size === 1) {
      agreement = `${present.length} sources agree`
    } else if (present.length === 1) {
      agreement = 'single source'
    }
    const selectedEntry = selection.value[key]
    const hasSelection = Boolean(selectedEntry?.source)
    const effectiveSource =
      (hasSelection ? present.find((column) => column.sourceKey === selectedEntry?.source) : undefined) ??
      present[0]
    const hasSuggested = Boolean(
      effectiveSource && columnHasField({ suggestion: effectiveSource.suggestion }, key),
    )
    return {
      key,
      label,
      current: options.current,
      checkbox: hasSuggested,
      checked: hasSelection && hasSuggested,
      checkboxSource: effectiveSource?.sourceKey ?? '',
      toggle: () =>
        toggleField(
          effectiveSource?.sourceKey ?? '',
          key,
          effectiveSource?.suggestion?.data ?? {},
        ),
      suggestSource: effectiveSource ? effectiveSource.source : undefined,
      saveSource: effectiveSource ? effectiveSource.sourceKey : undefined,
      saveData: effectiveSource?.suggestion?.data,
      agreement,
    }
  }

  const rows = [
    makeRow('title', 'Suggested title', { current: props.currentValues.title }),
    makeRow('date', 'Suggested date', { current: props.currentValues.date }),
    makeRow('correspondent', 'Suggested correspondent', {
      current: props.currentValues.correspondent,
    }),
    makeRow('tags', 'Suggested tags', {
      current: props.currentValues.tags || 'No tags',
    }),
  ]
  const hasNote = cols.some((column) => columnHasField({ suggestion: column.suggestion }, 'note'))
  if (hasNote) {
    rows.push(makeRow('note', 'Summary', { current: props.currentValues.note }))
  }
  return rows
})

const jumpToPage = (page: number | null | undefined) => {
  if (page) emit('jumpToPage', page)
}

const suggestionMetaLine = (source: string) => {
  const meta = suggestionsMeta.value?.[source]
  if (!meta) return ''
  const model = (meta as { model?: string }).model || 'unknown'
  const ocrModel = (meta as { ocr_model?: string | null }).ocr_model || ''
  const modelLabel = ocrModel ? `${ocrModel} / ${model}` : model
  const processed = (meta as { processed_at?: string }).processed_at
    ? formatDateTime((meta as { processed_at?: string }).processed_at)
    : 'unknown'
  return `Model: ${modelLabel} Â· Updated: ${processed}`
}

const fieldValue = (data: SuggestionPayload, field: string) => {
  if (!data) return ''
  const asString = (value: unknown) => (typeof value === 'string' ? value : '')
  if (field === 'title') return asString(data.title) || asString(data.suggested_title)
  if (field === 'date') return asString(data.date) || asString(data.suggested_document_date)
  if (field === 'correspondent')
    return asString(data.correspondent) || asString(data.suggested_correspondent)
  if (field === 'tags') return (data.tags ?? data.suggested_tags) || ''
  return data[field] ?? ''
}

const normalizedTags = (data: SuggestionPayload): string[] => {
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

const currentValueFor = (field: string) => {
  if (field === 'title') return props.currentValues.title
  if (field === 'date') return props.currentValues.date
  if (field === 'correspondent') return props.currentValues.correspondent
  if (field === 'tags') return props.currentValues.tags
  return ''
}

const isVariantBusy = (source: SuggestionSource) =>
  Object.entries(props.suggestionVariantLoading).some(
    ([key, value]) => key.startsWith(`${source}:`) && value,
  )

const isVariantLoading = (source: SuggestionSource, field: string) =>
  Boolean(props.suggestionVariantLoading[`${source}:${field}`])

// While a queued request waits for the model, show how long it has been running.
const waitLabel = (source: SuggestionSource, field: string) => {
  const seconds = props.suggestionVariantWait?.[`${source}:${field}`] ?? 0
  return seconds >= 3 ? `Generating... ${seconds}s` : 'Generating...'
}

const variantsFor = (source: SuggestionSource, field: string) =>
  props.suggestionVariants[`${source}:${field}`] || []

const variantError = (source: SuggestionSource, field: string) =>
  props.suggestionVariantError[`${source}:${field}`] || ''

const generateAllVariants = (source: SuggestionSource) => {
  suggestionFields.forEach((field) => requestSuggest(source, field.key))
}

const showVariantDialog = ref(false)
const variantDialog = ref<{ source: SuggestionSource; field: string; value: unknown } | null>(null)
const showApplyDialog = ref(false)
const applyDialog = ref<{ source: string; field: string; value: unknown; label: string } | null>(
  null,
)

const openVariantDialog = (source: SuggestionSource, field: string, value: unknown) => {
  variantDialog.value = { source, field, value }
  showVariantDialog.value = true
}

const closeVariantDialog = () => {
  showVariantDialog.value = false
  variantDialog.value = null
}

const confirmVariantUpdateSuggestion = () => {
  if (!variantDialog.value) return
  emit('applyVariant', variantDialog.value.source, variantDialog.value.field, variantDialog.value.value)
  closeVariantDialog()
}

const confirmVariantUpdateDocument = () => {
  if (!variantDialog.value) return
  emit(
    'applyVariantToDocument',
    variantDialog.value.source,
    variantDialog.value.field,
    variantDialog.value.value,
  )
  closeVariantDialog()
}

const suggestedValue = (data: SuggestionPayload, field: string): unknown => {
  let value: unknown = data[field]
  if (field === 'title') value = data.title || data.suggested_title || ''
  if (field === 'date') value = data.date || data.suggested_document_date || ''
  if (field === 'correspondent') value = data.correspondent || data.suggested_correspondent || ''
  if (field === 'tags') value = data.tags || data.suggested_tags || []
  if (field === 'note') value = data.summary || ''
  return value
}

type FieldSelection = { source: string; value?: unknown; tags?: string[] }
const selection = ref<Record<string, FieldSelection>>({})

const hasSuggestedValue = (data: SuggestionPayload, field: string) => {
  if (field === 'tags') return normalizedTags(data).length > 0
  const value = suggestedValue(data, field)
  return value !== null && value !== undefined && value !== ''
}

const isTagSelected = (source: string, tag: string) =>
  selection.value.tags?.source === source && Boolean(selection.value.tags.tags?.includes(tag))

const toggleField = (source: string, field: string, data: SuggestionPayload) => {
  const next = { ...selection.value }
  if (next[field]?.source === source) {
    delete next[field]
  } else if (field === 'tags') {
    next[field] = { source, tags: normalizedTags(data) }
  } else {
    next[field] = { source, value: suggestedValue(data, field) }
  }
  selection.value = next
}

const toggleTag = (source: string, tag: string) => {
  const current = selection.value.tags
  const next = { ...selection.value }
  if (!current || current.source !== source) {
    next.tags = { source, tags: [tag] }
  } else {
    const tags = current.tags || []
    const updated = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag]
    if (updated.length) next.tags = { source, tags: updated }
    else delete next.tags
  }
  selection.value = next
}

const clearSelection = () => {
  selection.value = {}
}

const selectionFieldOrder = ['title', 'date', 'correspondent', 'tags', 'note']
const selectionLabels: Record<string, string> = {
  title: 'Title',
  date: 'Date',
  correspondent: 'Correspondent',
  tags: 'Tags',
  note: 'Summary',
}

const TEXT_CANDIDATES_SOURCE = 'text_candidates'

// Reviewer guidance for "Suggest new": a passage marked in the document text and a hint.
const hint = ref('')
const focusText = ref('')
const guidanceNotice = ref('')
const guidanceTextRef = ref<HTMLElement | null>(null)
const activeTextSource = ref('')
const FOCUS_MAX_CHARS = 2000

const activeTextSourceText = computed(() => {
  const sources = props.textSources
  const match = sources.find((source) => source.key === activeTextSource.value) ?? sources[0]
  return match?.text ?? ''
})

watch(
  () => props.textSources.map((source) => source.key).join('|'),
  () => {
    if (!props.textSources.some((source) => source.key === activeTextSource.value)) {
      activeTextSource.value = props.textSources[0]?.key ?? ''
    }
  },
  { immediate: true },
)

const modelTextSource = ref<'' | 'paperless_ocr' | 'vision_ocr'>('')
const pagesInput = ref('')
const pagesInvalid = computed(
  () => Boolean(pagesInput.value.trim()) && !/^\d{1,4}(-\d{1,4})?(,\d{1,4}(-\d{1,4})?)*$/.test(pagesInput.value.replace(/\s+/g, '')),
)
const modelTextOptions = computed(() =>
  props.textSources.filter((source) => source.key === 'paperless_ocr' || source.key === 'vision_ocr'),
)

const guidanceActive = computed(() =>
  Boolean(focusText.value || hint.value.trim() || modelTextSource.value || pagesInput.value.trim()),
)
const focusPreview = computed(() =>
  focusText.value.length > 220 ? `${focusText.value.slice(0, 220)}…` : focusText.value,
)

const useSelectionAsFocus = () => {
  guidanceNotice.value = ''
  const selection = typeof window !== 'undefined' ? window.getSelection() : null
  const container = guidanceTextRef.value
  const selected = selection?.toString().trim() ?? ''
  const anchor = selection?.anchorNode ?? null
  if (!selected || !container || !anchor || !container.contains(anchor)) {
    guidanceNotice.value = 'Select a passage inside the document text first.'
    return
  }
  focusText.value = selected.slice(0, FOCUS_MAX_CHARS)
  if (selected.length > FOCUS_MAX_CHARS) {
    guidanceNotice.value = `Selection shortened to ${FOCUS_MAX_CHARS} characters.`
  }
  selection?.removeAllRanges()
}

const requestSuggest = (source: SuggestionSource, field: string) => {
  const guidance: {
    focus_text?: string
    hint?: string
    text_source?: 'paperless_ocr' | 'vision_ocr'
    pages?: string
  } = {}
  if (focusText.value) guidance.focus_text = focusText.value
  if (modelTextSource.value) guidance.text_source = modelTextSource.value
  const trimmedPages = pagesInput.value.replace(/\s+/g, '')
  if (trimmedPages) guidance.pages = trimmedPages
  const trimmedHint = hint.value.trim()
  if (trimmedHint) guidance.hint = trimmedHint
  if (Object.keys(guidance).length) emit('suggestField', source, field, guidance)
  else emit('suggestField', source, field)
}

const sourceLabel = (source: string) => {
  if (source === TEXT_CANDIDATES_SOURCE) return 'Text'
  return source === 'vision_ocr' ? 'Vision' : 'Paperless'
}

const dateCandidates = computed(() => props.textCandidates?.dates ?? [])
const correspondentCandidates = computed(() => props.textCandidates?.correspondents ?? [])
const hasTextCandidates = computed(
  () => dateCandidates.value.length > 0 || correspondentCandidates.value.length > 0,
)

const isCandidateSelected = (field: string, value: string) => {
  const entry = selection.value[field]
  return entry?.source === TEXT_CANDIDATES_SOURCE && entry.value === value
}

const toggleCandidate = (field: 'date' | 'correspondent', value: string) => {
  const next = { ...selection.value }
  if (isCandidateSelected(field, value)) {
    delete next[field]
  } else {
    next[field] = { source: TEXT_CANDIDATES_SOURCE, value }
  }
  selection.value = next
}

const candidateClass = (selected: boolean) =>
  selected
    ? 'border-emerald-400 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-100'
    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'

const CANDIDATE_LABELS: Record<string, string> = {
  issue: 'issue date',
  delivery: 'delivery',
  due: 'due',
  period: 'period',
  other: 'other',
}
const candidateLabel = (label: string) => CANDIDATE_LABELS[label] ?? label

const formatCandidateDate = (value: string) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  return match ? `${match[3]}.${match[2]}.${match[1]}` : value
}

const candidateTitle = (candidate: DateCandidate) => {
  const parts = [candidate.context]
  if (candidate.page) parts.push(`page ${candidate.page}`)
  return parts.filter(Boolean).join(' · ')
}

const selectedItems = computed(() =>
  selectionFieldOrder
    .filter((field) => selection.value[field])
    .map((field) => {
      const entry = selection.value[field] as FieldSelection
      if (field === 'tags') {
        const merged = mergeTagNames(props.currentTagList, entry.tags)
        return {
          field,
          label: selectionLabels[field],
          source: entry.source,
          current: props.currentValues.tags,
          next: merged.join(', '),
          value: merged as unknown,
        }
      }
      const value = entry.value
      return {
        field,
        label: selectionLabels[field],
        source: entry.source,
        current: field === 'note' ? props.currentValues.note : currentValueFor(field),
        next: typeof value === 'string' ? value : JSON.stringify(value),
        value,
      }
    }),
)

const applySelected = () => {
  if (!selectedItems.value.length) return
  emit(
    'applySelected',
    selectedItems.value.map((item) => ({
      source: item.source,
      field: item.field,
      value: item.value,
    })),
  )
}

const importDateOnly = (value: string) => {
  const match = value.trim().match(/^(\d{4}-\d{2}-\d{2})/)
  return match ? match[1] : ''
}

const applyPresetNoCorrespondent = () => {
  emit('applyToDocument', 'preset', 'correspondent', '')
}

const applyPresetIssueDateImport = () => {
  const dateOnly = importDateOnly(props.importDate)
  if (!dateOnly) return
  emit('applyToDocument', 'preset', 'date', dateOnly)
}

watch(
  () => props.applying,
  (now, before) => {
    if (before && !now) clearSelection()
  },
)

const openApplyDialog = (source: string, field: string, data: SuggestionPayload) => {
  const value = suggestedValue(data, field)
  if (field === 'tags' && (!Array.isArray(value) || value.length === 0)) return
  if (value === null || value === undefined || value === '') return
  const label = typeof value === 'string' ? value : JSON.stringify(value)
  applyDialog.value = { source, field, value, label }
  showApplyDialog.value = true
}

const closeApplyDialog = () => {
  showApplyDialog.value = false
  applyDialog.value = null
}

const confirmApplyToDocument = () => {
  if (!applyDialog.value) return
  emit('applyToDocument', applyDialog.value.source, applyDialog.value.field, applyDialog.value.value)
  closeApplyDialog()
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
</script>
