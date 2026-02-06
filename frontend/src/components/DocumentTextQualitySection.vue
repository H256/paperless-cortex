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
    >
      <div class="flex items-center justify-between">
        <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Text quality (baseline)
        </div>
        <span
          v-if="contentQuality"
          class="rounded-full px-2 py-1 text-xs font-semibold"
          :class="scoreClass"
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

    <div
      class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800"
    >
      <div class="flex items-center justify-between">
        <div
          class="text-sm font-semibold text-slate-700 dark:text-slate-200"
          title="Composite OCR score stored per source. Lower is better. Uses text noise heuristics and an optional logprob penalty."
        >
          OCR quality (stored)
        </div>
        <span class="text-xs font-semibold text-slate-500 dark:text-slate-400" title="Lower is better">
          Lower is better
        </span>
      </div>
      <div v-if="ocrScoresError" class="mt-2 text-sm text-rose-600 dark:text-rose-300">
        {{ ocrScoresError }}
      </div>
      <div v-else-if="ocrScoresLoading" class="mt-2 text-sm text-slate-500 dark:text-slate-400">
        Loading OCR scores...
      </div>
      <div v-else-if="!ocrScores.length" class="mt-2 text-sm text-slate-500 dark:text-slate-400">
        No OCR score data available yet.
      </div>
      <div v-else class="mt-3 grid gap-3 md:grid-cols-2">
        <div
          v-for="score in normalizedScores"
          :key="score.source"
          class="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        >
          <div class="flex items-center justify-between">
            <div class="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {{ score.label }}
            </div>
            <span
              class="rounded-full px-2 py-1 text-[11px] font-semibold"
              :class="scoreBadge(score)"
              title="Composite OCR score including heuristic noise penalty and optional logprob penalty."
            >
              {{ formatScore(score.quality_score) }} · {{ score.verdict || 'n/a' }}
            </span>
          </div>
          <div class="mt-2 space-y-1">
            <div class="flex items-center justify-between">
              <span
                class="text-[11px] text-slate-500 dark:text-slate-400"
                title="Penalty from text-noise heuristics (weird chars, repeats, short words, line length)."
              >
                Heuristics
              </span>
              <span>{{ formatScore(score.components?.heuristics) }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span
                class="text-[11px] text-slate-500 dark:text-slate-400"
                title="Penalty derived from logprob-based pseudo perplexity (if enabled)."
              >
                Logprob penalty
              </span>
              <span>{{ formatScore(score.components?.ppl_penalty) }}</span>
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
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { DocumentOcrScoreOut, TextQualityMetrics } from '@/api/generated/model'
import { computed } from 'vue'

const props = defineProps<{
  content: string
  contentQuality: TextQualityMetrics | null
  contentQualityError: string
  ocrScores: DocumentOcrScoreOut[]
  ocrScoresLoading: boolean
  ocrScoresError: string
}>()

const scoreClass = computed(() => {
  if (!props.contentQuality) return ''
  if (props.contentQuality.score >= 80) return 'bg-emerald-100 text-emerald-700'
  if (props.contentQuality.score >= 60) return 'bg-amber-100 text-amber-700'
  return 'bg-rose-100 text-rose-700'
})

const normalizedScores = computed(() =>
  props.ocrScores.map((score) => ({
    ...score,
    label: score.source === 'vision_ocr' ? 'Vision OCR' : 'Paperless OCR',
  })),
)

const formatScore = (value?: number | null) => {
  if (value === null || value === undefined) return 'n/a'
  return value.toFixed(2)
}

const scoreBadge = (score: DocumentOcrScoreOut) => {
  const value = score.quality_score ?? 0
  if (value >= 55) return 'bg-rose-100 text-rose-700'
  if (value >= 32) return 'bg-amber-100 text-amber-700'
  return 'bg-emerald-100 text-emerald-700'
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
