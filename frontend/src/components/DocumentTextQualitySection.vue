<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Text layer</h3>
      <span class="text-xs font-semibold text-slate-500 dark:text-slate-400">Baseline OCR</span>
    </div>
    <textarea
      class="mt-4 w-full min-h-[260px] rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      readonly
      :value="content"
    ></textarea>

    <div
      class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
      data-testid="readability"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div
          class="text-sm font-semibold text-slate-700 dark:text-slate-200"
          title="One scale per OCR text: 100 is clean, 0 is unreadable. Derived from noise heuristics and, when the model server provides it, a perplexity penalty."
        >
          Readability of the OCR texts
        </div>
        <span class="text-xs font-semibold text-slate-500 dark:text-slate-400">
          0 – 100, higher is better
        </span>
      </div>

      <div v-if="ocrScoresError" class="mt-2 text-sm text-rose-600 dark:text-rose-300">
        {{ ocrScoresError }}
      </div>
      <div v-else-if="ocrScoresLoading" class="mt-2 text-sm text-slate-500 dark:text-slate-400">
        Loading OCR scores...
      </div>
      <div v-else-if="!normalizedScores.length" class="mt-2 text-sm text-slate-500 dark:text-slate-400">
        No OCR score data available yet.
      </div>
      <template v-else>
        <div
          class="mt-3 flex flex-wrap items-center gap-2 text-xs"
          data-testid="source-comparison"
        >
          <span
            v-if="recommendedLabel"
            class="rounded-full border border-emerald-300 bg-emerald-50 px-2 py-1 font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200"
            data-testid="recommended-source"
            :title="ocrComparison?.reason || ''"
          >
            Better text: {{ recommendedLabel }}
          </span>
          <span
            v-else-if="ocrComparison?.reason"
            class="rounded-full border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            data-testid="no-recommendation"
          >
            {{ ocrComparison.reason }}
          </span>
          <span
            v-if="agreementPercent !== null"
            class="rounded-full border px-2 py-1 font-semibold"
            :class="agreementClass"
            data-testid="agreement"
            title="Share of distinct words that both OCR texts contain. Low values mean the two texts differ in content."
          >
            Texts agree {{ agreementPercent }}%
          </span>
          <span v-if="recommendedLabel && ocrComparison?.reason" class="text-slate-500 dark:text-slate-400">
            {{ ocrComparison.reason }}
          </span>
        </div>

        <div class="mt-3 grid gap-3 md:grid-cols-2">
          <div
            v-for="score in normalizedScores"
            :key="score.source"
            class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            :data-testid="`readability-${score.source}`"
          >
            <div class="flex items-center justify-between">
              <div
                class="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
              >
                {{ score.label }}
              </div>
              <span
                class="rounded-full px-2 py-1 text-[11px] font-semibold"
                :class="score.badge"
                :title="`Total penalty ${formatScore(score.quality_score)} (lower is better); verdict ${score.verdict || 'n/a'}`"
              >
                {{ score.readabilityLabel }}
              </span>
            </div>
            <div class="mt-2 space-y-1">
              <div class="flex items-center justify-between">
                <span
                  class="text-[11px] text-slate-500 dark:text-slate-400"
                  title="Perplexity of the text under the language model. Needs a server that returns prompt logprobs."
                >
                  Language model check
                </span>
                <span :class="score.pplMeasured ? '' : 'text-slate-400 dark:text-slate-500'">
                  {{ score.pplLabel }}
                </span>
              </div>
              <div v-if="score.model_name" class="flex items-center justify-between">
                <span class="text-[11px] text-slate-500 dark:text-slate-400">Model</span>
                <span>{{ score.model_name }}</span>
              </div>
              <div v-if="score.processed_at" class="flex items-center justify-between">
                <span class="text-[11px] text-slate-500 dark:text-slate-400">Updated</span>
                <span>{{ formatDateTime(score.processed_at) }}</span>
              </div>
            </div>
            <details class="mt-2">
              <summary class="cursor-pointer text-[11px] font-semibold text-slate-500">
                Penalties
              </summary>
              <div class="mt-1 space-y-1 text-[11px] text-slate-600 dark:text-slate-300">
                <div class="flex items-center justify-between">
                  <span>Noise heuristics</span>
                  <span>{{ formatScore(score.components?.heuristics) }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span>Perplexity</span>
                  <span>{{ score.pplMeasured ? formatScore(score.components?.ppl_penalty) : 'not measured' }}</span>
                </div>
                <div class="flex items-center justify-between font-semibold">
                  <span>Total (lower is better)</span>
                  <span>{{ formatScore(score.quality_score) }}</span>
                </div>
              </div>
            </details>
          </div>
        </div>
      </template>

      <details class="mt-3 text-[11px] text-slate-600 dark:text-slate-300">
        <summary class="cursor-pointer font-semibold text-slate-500">How is this computed?</summary>
        <div class="mt-2 space-y-1 rounded-md border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900">
          <div>
            <span class="font-semibold">Readability</span> = 100 minus the penalty of the text.
          </div>
          <div>
            <span class="font-semibold">Noise heuristics</span>: weird characters, repeats, short words,
            odd line lengths.
          </div>
          <div>
            <span class="font-semibold">Language model check</span>: perplexity from prompt logprobs;
            "not measured" when the model server does not return them.
          </div>
          <div>
            <span class="font-semibold">Texts agree</span>: share of distinct words that Paperless OCR and
            Vision OCR have in common. It does not look at layout or reading order.
          </div>
        </div>
      </details>
    </div>

    <div
      class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
    >
      <div class="flex items-center justify-between">
        <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Basic text check (Paperless text)
        </div>
        <span
          v-if="contentQuality"
          class="rounded-full px-2 py-1 text-xs font-semibold"
          :class="scoreClass"
          title="0 – 100, higher is better"
        >
          {{ contentQuality.score }} / 100
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
          <summary class="cursor-pointer text-xs font-semibold text-slate-500">Show metrics</summary>
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
</template>

<script setup lang="ts">
import type { DocumentOcrScoreOut, TextQualityMetrics } from '@/api/generated/model'
import { computed } from 'vue'

type OcrComparison = {
  agreement: number | null
  recommendedSource: string | null
  reason: string | null
}

const props = withDefaults(
  defineProps<{
    content: string
    contentQuality: TextQualityMetrics | null
    contentQualityError: string
    ocrScores: DocumentOcrScoreOut[]
    ocrScoresLoading: boolean
    ocrScoresError: string
    ocrComparison?: OcrComparison | null
  }>(),
  { ocrComparison: null },
)

const SOURCE_LABELS: Record<string, string> = {
  vision_ocr: 'Vision OCR',
  paperless_ocr: 'Paperless OCR',
}

// Single scale: readability = 100 - penalty (higher is better).
const readabilityOf = (score: DocumentOcrScoreOut) => {
  if (score.quality_score === null || score.quality_score === undefined) return null
  return Math.max(0, Math.min(100, Math.round(100 - score.quality_score)))
}

const readabilityBadge = (value: number | null) => {
  if (value === null) return 'bg-slate-100 text-slate-600'
  if (value >= 68) return 'bg-emerald-100 text-emerald-700'
  if (value >= 45) return 'bg-amber-100 text-amber-700'
  return 'bg-rose-100 text-rose-700'
}

const scoreClass = computed(() => {
  if (!props.contentQuality) return ''
  if (props.contentQuality.score >= 80) return 'bg-emerald-100 text-emerald-700'
  if (props.contentQuality.score >= 60) return 'bg-amber-100 text-amber-700'
  return 'bg-rose-100 text-rose-700'
})

const normalizedScores = computed(() =>
  props.ocrScores.map((score) => {
    const readability = readabilityOf(score)
    const pplInfo = (score.ppl ?? {}) as { supported?: boolean; reason?: string; ppl?: number }
    const pplMeasured = pplInfo.supported === true
    return {
      ...score,
      label: SOURCE_LABELS[score.source] ?? score.source,
      badge: readabilityBadge(readability),
      readabilityLabel:
        readability === null ? 'n/a' : `${readability} / 100 · ${score.verdict || 'n/a'}`,
      pplMeasured,
      pplLabel: pplMeasured
        ? `perplexity ${Number(pplInfo.ppl ?? 0).toFixed(1)}`
        : `not measured${pplInfo.reason ? ` (${pplInfo.reason})` : ''}`,
    }
  }),
)

const recommendedLabel = computed(() => {
  const source = props.ocrComparison?.recommendedSource
  return source ? (SOURCE_LABELS[source] ?? source) : ''
})

const agreementPercent = computed(() => {
  const value = props.ocrComparison?.agreement
  return value === null || value === undefined ? null : Math.round(value * 100)
})

const agreementClass = computed(() => {
  const value = agreementPercent.value ?? 0
  if (value >= 70)
    return 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200'
  if (value >= 50)
    return 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200'
  return 'border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-200'
})

const formatScore = (value?: number | null) => {
  if (value === null || value === undefined) return 'n/a'
  return value.toFixed(2)
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
