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
      <div class="grid gap-4 lg:grid-cols-2">
        <div
          v-for="panel in orderedPanels"
          :key="panel.key"
          class="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
          :class="panel.key === 'similar_docs' ? 'lg:col-span-2' : ''"
        >
          <div class="flex items-center justify-between">
            <strong class="text-sm text-slate-900 dark:text-slate-100">{{ panel.label }}</strong>
            <div v-if="panel.allowActions" class="flex items-center gap-2">
              <button
                class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                :disabled="suggestionsLoading || isVariantBusy(panel.source)"
                @click="emit('refresh', panel.source)"
              >
                Refresh
              </button>
              <button
                class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                :disabled="suggestionsLoading || isVariantBusy(panel.source)"
                title="Generate alternative values for all suggestion fields."
                @click="generateAllVariants(panel.source)"
              >
                <span v-if="isVariantBusy(panel.source)" class="inline-flex items-center gap-2">
                  <Loader2 class="h-3.5 w-3.5 animate-spin" />
                  Generating...
                </span>
                <span v-else>Generate variants</span>
              </button>
            </div>
          </div>

          <div
            v-if="suggestionMetaLine(panel.source)"
            class="mt-2 text-xs text-slate-500 dark:text-slate-400"
          >
            {{ suggestionMetaLine(panel.source) }}
          </div>

          <div v-if="!panel.suggestion" class="mt-3 text-sm text-slate-500 dark:text-slate-400">
            <em>No data.</em>
          </div>
          <div v-else class="mt-3 space-y-3">
            <div v-if="panel.suggestion.raw">
              <div class="text-xs font-semibold text-slate-500">Raw output</div>
              <pre
                class="mt-1 max-h-40 overflow-auto rounded-md border border-slate-200 bg-white p-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                >{{ panel.suggestion.raw }}</pre
              >
            </div>

            <div v-if="panel.suggestion.data" class="space-y-2">
              <div v-if="panel.showSummary" class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <div class="flex items-start gap-2">
                  <span>Summary</span>
                  <span
                    v-if="currentValues.note"
                    class="inline-flex items-center text-slate-400"
                    :title="currentValues.note"
                  >
                    <Info class="h-3.5 w-3.5" />
                  </span>
                </div>
                <button
                  v-if="panel.allowActions"
                  class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                  :disabled="suggestionsLoading || isVariantLoading(panel.source, 'note')"
                  @click="emit('suggestField', panel.source, 'note')"
                >
                  <span
                    v-if="isVariantLoading(panel.source, 'note')"
                    class="inline-flex items-center gap-2"
                  >
                    <Loader2 class="h-3.5 w-3.5 animate-spin" />
                    Generating...
                  </span>
                  <span v-else>Suggest new</span>
                </button>
                <button
                  v-if="panel.allowNoteSave"
                  class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                  :disabled="suggestionsLoading"
                  @click="openApplyDialog(panel.sourceKey, 'note', panel.suggestion.data)"
                >
                  Save note
                </button>
              </div>
              <div v-if="panel.showSummary" class="text-sm text-slate-900 dark:text-slate-100">
                {{ panel.suggestion.data.summary }}
              </div>
              <div
                v-if="
                  panel.allowActions &&
                  panel.showSummary &&
                  (variantError(panel.source, 'note') ||
                    isVariantLoading(panel.source, 'note') ||
                    (variantsFor(panel.source, 'note') || []).length)
                "
                class="rounded-md border border-dashed border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900"
              >
                <div class="text-xs font-semibold text-slate-500 dark:text-slate-300">
                  Summary variants
                </div>
                <div v-if="variantError(panel.source, 'note')" class="mt-2 text-xs text-rose-600">
                  {{ variantError(panel.source, 'note') }}
                </div>
                <div
                  v-else-if="isVariantLoading(panel.source, 'note')"
                  class="mt-2 inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400"
                >
                  <Loader2 class="h-3.5 w-3.5 animate-spin" />
                  Generating variants...
                </div>
                <div
                  v-else
                  v-for="(variant, index) in variantsFor(panel.source, 'note')"
                  :key="`${panel.key}-note-${index}-${variant}`"
                  class="mt-2 flex items-start justify-between gap-2 text-xs"
                  :class="index > 0 ? 'border-t border-slate-200 pt-2 dark:border-slate-700' : ''"
                >
                  <span class="text-slate-700 dark:text-slate-200">{{ variant }}</span>
                  <button
                    class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                    @click="openVariantDialog(panel.source, 'note', variant)"
                  >
                    Apply
                  </button>
                </div>
              </div>
              <div v-if="panel.showMeta" class="grid gap-2">
                <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                  <span>Document type</span>
                  <span class="text-slate-900 dark:text-slate-100">{{
                    panel.suggestion.data.documentType ||
                    panel.suggestion.data.suggested_document_type
                  }}</span>
                </div>
                <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                  <span>Language</span>
                  <span class="text-slate-900 dark:text-slate-100">{{
                    panel.suggestion.data.language
                  }}</span>
                </div>
              </div>

              <div
                v-for="field in fieldsForPanel(panel)"
                :key="`${panel.key}-${field.key}`"
                class="grid grid-cols-1 gap-2 border-t border-slate-200 pt-2 md:grid-cols-[140px_1fr_auto]"
              >
                <span class="text-xs text-slate-500 dark:text-slate-400">{{ field.label }}</span>
                <div class="min-w-0 text-sm text-slate-900 dark:text-slate-100">
                  <template v-if="field.key === 'tags'">
                    <div
                      v-if="normalizedTags(panel.suggestion.data).length"
                      class="flex flex-wrap gap-1.5"
                    >
                      <span
                        v-for="tag in normalizedTags(panel.suggestion.data)"
                        :key="`tag-${panel.key}-${tag}`"
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
                    <span class="break-words">{{ fieldValue(panel.suggestion.data, field.key) }}</span>
                  </template>
                  <div class="mt-1 break-words text-xs text-slate-500 dark:text-slate-400">
                    Current:
                    {{
                      field.key === 'tags'
                        ? currentValues.tags || 'No tags'
                        : currentValueFor(field.key) || 'â€”'
                    }}
                  </div>
                  <div
                    v-if="
                      panel.allowActions &&
                      (variantError(panel.source, field.key) ||
                        isVariantLoading(panel.source, field.key) ||
                        (variantsFor(panel.source, field.key) || []).length)
                    "
                    class="mt-2 rounded-md border border-dashed border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900"
                  >
                    <div class="text-xs font-semibold text-slate-500 dark:text-slate-300">
                      Variants for {{ field.label }}
                    </div>
                    <div v-if="variantError(panel.source, field.key)" class="mt-2 text-xs text-rose-600">
                      {{ variantError(panel.source, field.key) }}
                    </div>
                    <div
                      v-else-if="isVariantLoading(panel.source, field.key)"
                      class="mt-2 inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400"
                    >
                      <Loader2 class="h-3.5 w-3.5 animate-spin" />
                      Generating variants...
                    </div>
                    <div
                      v-else
                      v-for="(variant, index) in variantsFor(panel.source, field.key)"
                      :key="`${panel.key}-${field.key}-${index}-${variant}`"
                      class="mt-2 flex items-center justify-between gap-2 text-xs"
                    >
                      <span class="text-slate-700 dark:text-slate-200">{{
                        Array.isArray(variant) ? variant.join(', ') : variant
                      }}</span>
                      <button
                        class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-500"
                        :disabled="suggestionsLoading"
                        @click="openVariantDialog(panel.source, field.key, variant)"
                      >
                        Use
                      </button>
                    </div>
                  </div>
                </div>
                <div class="flex items-start gap-2">
                  <button
                    v-if="panel.allowActions"
                    class="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
                    :disabled="suggestionsLoading || isVariantLoading(panel.source, field.key)"
                    @click="emit('suggestField', panel.source, field.key)"
                  >
                    <span
                      v-if="isVariantLoading(panel.source, field.key)"
                      class="inline-flex items-center gap-2"
                    >
                      <Loader2 class="h-3.5 w-3.5 animate-spin" />
                      Generating...
                    </span>
                    <span v-else>Suggest new</span>
                  </button>
                  <button
                    class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:border-emerald-300 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200"
                    :disabled="suggestionsLoading"
                    @click="openApplyDialog(panel.sourceKey, field.key, panel.suggestion.data)"
                  >
                    Save
                  </button>
                </div>
              </div>

            </div>
          </div>
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
import { computed, ref } from 'vue'
import { Info, Loader2 } from 'lucide-vue-next'
import ChoiceDialog from './ChoiceDialog.vue'
import ConfirmDialog from './ConfirmDialog.vue'

type SuggestionPayload = Record<string, unknown>
type SuggestionSource = 'paperless_ocr' | 'vision_ocr' | 'similar_docs'
type SuggestionState = {
  paperless_ocr?: SuggestionPayload
  vision_ocr?: SuggestionPayload
  similar_docs?: SuggestionPayload
  suggestions_meta?: Record<string, unknown>
}

const props = defineProps<{
  suggestions: SuggestionState | null
  suggestionsError: string
  suggestionsLoading: boolean
  suggestionVariants: Record<string, unknown[]>
  suggestionVariantLoading: Record<string, boolean>
  suggestionVariantError: Record<string, string>
  currentValues: {
    title: string
    date: string
    correspondent: string
    tags: string
    note: string
  }
}>()

const emit = defineEmits<{
  (e: 'refresh', source: SuggestionSource): void
  (e: 'suggestField', source: SuggestionSource, field: string): void
  (e: 'applyVariant', source: SuggestionSource, field: string, value: unknown): void
  (e: 'applyVariantToDocument', source: SuggestionSource, field: string, value: unknown): void
  (e: 'applyToDocument', source: string, field: string, value: unknown): void
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

const panelFor = (key: 'paperless_ocr' | 'vision_ocr' | 'similar_docs') =>
  normalizeSuggestion(props.suggestions?.[key])

const panels = computed(() => [
  {
    key: 'vision_ocr',
    label: 'Vision OCR',
    source: 'vision_ocr' as const,
    sourceKey: 'vision_ocr',
    allowActions: true,
    allowNoteSave: true,
    showSummary: true,
    showMeta: true,
    suggestion: panelFor('vision_ocr'),
  },
  {
    key: 'paperless_ocr',
    label: 'Paperless OCR',
    source: 'paperless_ocr' as const,
    sourceKey: 'paperless_ocr',
    allowActions: true,
    allowNoteSave: true,
    showSummary: true,
    showMeta: true,
    suggestion: panelFor('paperless_ocr'),
  },
  {
    key: 'similar_docs',
    label: 'Similar docs',
    source: 'similar_docs' as const,
    sourceKey: 'similar_docs',
    allowActions: false,
    allowNoteSave: false,
    showSummary: false,
    showMeta: true,
    suggestion: panelFor('similar_docs'),
  },
])

const orderedPanels = computed(() => panels.value)

const fieldsForPanel = (panel: { key: string }) => {
  if (panel.key === 'similar_docs') {
    return suggestionFields.filter((field) => field.key === 'correspondent' || field.key === 'tags')
  }
  return suggestionFields
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

const variantsFor = (source: SuggestionSource, field: string) =>
  props.suggestionVariants[`${source}:${field}`] || []

const variantError = (source: SuggestionSource, field: string) =>
  props.suggestionVariantError[`${source}:${field}`] || ''

const generateAllVariants = (source: SuggestionSource) => {
  suggestionFields.forEach((field) => emit('suggestField', source, field.key))
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

const openApplyDialog = (source: string, field: string, data: SuggestionPayload) => {
  let value: unknown = data[field]
  if (field === 'title') value = data.title || data.suggested_title || ''
  if (field === 'date') value = data.date || data.suggested_document_date || ''
  if (field === 'correspondent') value = data.correspondent || data.suggested_correspondent || ''
  if (field === 'tags') value = data.tags || data.suggested_tags || []
  if (field === 'note') value = data.summary || ''
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
