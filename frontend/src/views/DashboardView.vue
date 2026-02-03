<template>
  <section>
    <div>
      <div class="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 class="text-3xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Dashboard</h2>
          <p class="text-sm text-slate-500 dark:text-slate-400">Visual overview of processing status and document mix.</p>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
          :disabled="loading"
          @click="load"
        >
          <RefreshCcw class="h-4 w-4" :class="{ 'animate-spin': loading }" />
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>

        <div v-if="error" class="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/40 dark:text-rose-200">
          {{ error }}
        </div>

      <template v-else>
        <div class="grid gap-4 lg:grid-cols-6">
          <div class="lg:col-span-4">
            <div class="mb-6 flex items-center justify-start">
              <img
                src="/cortex_image_transparent.png"
                alt="Paperless-NGX Cortex"
                class="h-28 w-auto object-contain opacity-90"
              />
            </div>
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Documents</div>
                <div class="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100">{{ stats.total }}</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Total synced</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Fully processed</div>
                <div class="mt-3 text-3xl font-semibold text-emerald-600">{{ stats.fully_processed }}</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">All tasks complete</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Unprocessed</div>
                <div class="mt-3 text-3xl font-semibold text-amber-600">{{ stats.unprocessed }}</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Missing intelligence</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Embeddings</div>
                <div class="mt-3 text-2xl font-semibold text-indigo-600">{{ stats.embeddings }}</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Vectorized docs</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Vision OCR</div>
                <div class="mt-3 text-2xl font-semibold text-sky-500">{{ stats.vision }}</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Vision pages stored</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Suggestions</div>
                <div class="mt-3 text-2xl font-semibold text-purple-500">{{ stats.suggestions }}</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">AI metadata ready</div>
              </div>
            </div>

            <div class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div class="flex items-center justify-between">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Processing status</div>
                  <div class="mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                    {{ processedPercent }}% processed
                  </div>
                </div>
                <div class="text-sm text-slate-500 dark:text-slate-400">
                  {{ stats.fully_processed }} / {{ stats.total }}
                </div>
              </div>
              <div class="mt-4 h-3 w-full rounded-full bg-slate-100 dark:bg-slate-800">
                <div class="h-3 rounded-full bg-gradient-to-r from-indigo-500 via-emerald-500 to-sky-400" :style="{ width: processedPercent + '%' }"></div>
              </div>
            </div>
          </div>

          <div class="lg:col-span-2">
            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Tags (top)</div>
              <div class="mt-4 flex items-center gap-6">
                <div class="h-28 w-28 rounded-full" :style="donutStyle"></div>
                <div class="space-y-2 text-xs text-slate-500 dark:text-slate-400">
                  <div v-for="slice in tagSlices" :key="slice.name" class="flex items-center gap-2">
                    <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: slice.color }"></span>
                    <span class="text-slate-700 dark:text-slate-200">{{ slice.name }}</span>
                    <span class="ml-auto text-slate-400">{{ slice.count }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Page count</div>
              <div class="mt-4 space-y-2">
                <div v-for="bucket in pageCounts" :key="bucket.label" class="text-xs text-slate-500 dark:text-slate-400">
                  <div class="flex items-center justify-between">
                    <span class="text-slate-700 dark:text-slate-200">{{ bucket.label }}</span>
                    <span>{{ bucket.count }}</span>
                  </div>
                  <div class="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div
                      class="h-2 rounded-full bg-indigo-500"
                      :style="{ width: bucketPercent(bucket.count) + '%' }"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-6 grid gap-4 lg:grid-cols-2">
          <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div class="flex items-center justify-between">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Top correspondents</div>
              <span class="text-xs text-slate-400">{{ topCorrespondents.length }}</span>
            </div>
            <div class="mt-4 space-y-3">
              <div v-for="item in topCorrespondents" :key="item.name" class="text-xs text-slate-500 dark:text-slate-400">
                <div class="flex items-center justify-between">
                  <span class="text-slate-800 dark:text-slate-200">{{ item.name }}</span>
                  <span>{{ item.count }}</span>
                </div>
                <div class="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                  <div class="h-2 rounded-full bg-amber-400" :style="{ width: barPercent(item.count, topCorrespondentsMax) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">All correspondents</div>
            <div class="mt-4 max-h-72 space-y-2 overflow-auto pr-2 text-xs text-slate-600 dark:text-slate-300">
              <div v-for="item in correspondents" :key="item.name" class="flex items-center justify-between">
                <span>{{ item.name }}</span>
                <span class="text-slate-400">{{ item.count }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-10 rounded-3xl border border-slate-200 bg-white/90 p-8 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Erweitert</div>
              <div class="mt-2 text-xl font-semibold text-slate-900 dark:text-slate-100">Deep dive on processing and structure</div>
            </div>
            <div class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white p-1 text-xs font-semibold text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
              <button
                class="rounded-full px-3 py-1 transition"
                :class="monthlyRange === '12' ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900' : ''"
                @click="monthlyRange = '12'"
              >
                12 Monate
              </button>
              <button
                class="rounded-full px-3 py-1 transition"
                :class="monthlyRange === '24' ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900' : ''"
                @click="monthlyRange = '24'"
              >
                24 Monate
              </button>
              <button
                class="rounded-full px-3 py-1 transition"
                :class="monthlyRange === 'all' ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900' : ''"
                @click="monthlyRange = 'all'"
              >
                Alle
              </button>
            </div>
          </div>

          <div class="mt-8 grid gap-6 lg:grid-cols-3">
            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div class="flex items-center justify-between">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Monthly processing</div>
                <div class="text-[11px] text-slate-400">processed vs. open</div>
              </div>
              <div class="mt-5 flex items-end gap-3 overflow-x-auto pb-2">
                <div
                  v-for="item in monthlySeries"
                  :key="item.label"
                  class="flex w-12 flex-shrink-0 flex-col items-center gap-2 text-[10px] text-slate-400"
                >
                  <div
                    class="flex h-28 w-7 flex-col-reverse overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
                    :title="`${item.label}: ${item.processed} processed / ${item.unprocessed} open`"
                  >
                    <div
                      class="bg-emerald-400"
                      :style="{ height: (item.processed / monthlyMax) * 100 + '%' }"
                      title="Processed"
                    ></div>
                    <div
                      class="bg-amber-400"
                      :style="{ height: (item.unprocessed / monthlyMax) * 100 + '%' }"
                      title="Unprocessed"
                    ></div>
                  </div>
                  <span>{{ item.label }}</span>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Unprocessed by correspondent</div>
              <div class="mt-4 space-y-2 text-xs text-slate-500 dark:text-slate-400">
                <div v-for="item in unprocessedByCorrespondent.slice(0, 8)" :key="item.name">
                  <div class="flex items-center justify-between">
                    <span class="text-slate-700 dark:text-slate-200">{{ item.name }}</span>
                    <span>{{ item.count }}</span>
                  </div>
                  <div class="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div class="h-2 rounded-full bg-rose-400" :style="{ width: barPercent(item.count, unprocessedMax) + '%' }"></div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Document types</div>
              <div class="mt-4 space-y-2 text-xs text-slate-500 dark:text-slate-400">
                <div v-for="item in docTypes.slice(0, 8)" :key="item.name">
                  <div class="flex items-center justify-between">
                    <span class="text-slate-700 dark:text-slate-200">{{ item.name }}</span>
                    <span>{{ item.count }}</span>
                  </div>
                  <div class="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div class="h-2 rounded-full bg-indigo-400" :style="{ width: barPercent(item.count, docTypeMax) + '%' }"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RefreshCcw } from 'lucide-vue-next';
import { getDashboard } from '../services/documents';

type DashboardCount = { id?: number | null; name: string; count: number };
type PageCountBucket = { label: string; count: number };
type DashboardPayload = {
  stats: {
    total: number;
    processed: number;
    unprocessed: number;
    embeddings: number;
    vision: number;
    suggestions: number;
    fully_processed: number;
  };
  correspondents: DashboardCount[];
  top_correspondents: DashboardCount[];
  tags: DashboardCount[];
  top_tags: DashboardCount[];
  page_counts: PageCountBucket[];
  document_types: DashboardCount[];
  unprocessed_by_correspondent: DashboardCount[];
  monthly_processing: { label: string; total: number; processed: number; unprocessed: number }[];
};

const loading = ref(false);
const error = ref('');
const data = ref<DashboardPayload | null>(null);

const stats = computed(() => data.value?.stats ?? {
  total: 0,
  processed: 0,
  unprocessed: 0,
  embeddings: 0,
  vision: 0,
  suggestions: 0,
  fully_processed: 0,
});
const correspondents = computed(() => data.value?.correspondents ?? []);
const topCorrespondents = computed(() => data.value?.top_correspondents ?? []);
const pageCounts = computed(() => data.value?.page_counts ?? []);
const docTypes = computed(() => data.value?.document_types ?? []);
const unprocessedByCorrespondent = computed(() => data.value?.unprocessed_by_correspondent ?? []);
const monthlyProcessing = computed(() => data.value?.monthly_processing ?? []);
const monthlyRange = ref<'12' | '24' | 'all'>('24');
const tags = computed(() => data.value?.tags ?? []);
const topTags = computed(() => data.value?.top_tags ?? []);

const processedPercent = computed(() => {
  if (!stats.value.total) return 0;
  return Math.min(100, Math.round((stats.value.fully_processed / stats.value.total) * 100));
});

const topCorrespondentsMax = computed(() => Math.max(1, ...topCorrespondents.value.map((item) => item.count)));

const tagPalette = [
  '#6366f1',
  '#0ea5e9',
  '#14b8a6',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#22c55e',
  '#eab308',
];

const tagSlices = computed(() => {
  const slices = topTags.value.map((tag, index) => ({
    name: tag.name,
    count: tag.count,
    color: tagPalette[index % tagPalette.length],
  }));
  const total = tags.value.reduce((sum, item) => sum + item.count, 0);
  const sliceTotal = slices.reduce((sum, item) => sum + item.count, 0);
  const remainder = total - sliceTotal;
  if (remainder > 0) {
    slices.push({ name: 'Other', count: remainder, color: '#94a3b8' });
  }
  return slices;
});

const donutStyle = computed(() => {
  const total = tagSlices.value.reduce((sum, item) => sum + item.count, 0);
  if (!total) return { background: '#e2e8f0' };
  let cumulative = 0;
  const stops = tagSlices.value.map((slice) => {
    const start = (cumulative / total) * 100;
    cumulative += slice.count;
    const end = (cumulative / total) * 100;
    return `${slice.color} ${start}% ${end}%`;
  });
  return {
    background: `conic-gradient(${stops.join(', ')})`,
  };
});

const bucketPercent = (count: number) => {
  const total = pageCounts.value.reduce((sum, item) => sum + item.count, 0);
  if (!total) return 0;
  return Math.round((count / total) * 100);
};

const barPercent = (value: number, max: number) => {
  if (!max) return 0;
  return Math.round((value / max) * 100);
};

const monthlySeries = computed(() => {
  if (!monthlyProcessing.value.length) return [];
  if (monthlyRange.value === 'all') return monthlyProcessing.value;
  const windowSize = monthlyRange.value === '12' ? 12 : 24;
  return monthlyProcessing.value.slice(-windowSize);
});
const monthlyMax = computed(() => Math.max(1, ...monthlySeries.value.map((item) => item.total)));
const docTypeMax = computed(() => Math.max(1, ...docTypes.value.map((item) => item.count)));
const unprocessedMax = computed(() => Math.max(1, ...unprocessedByCorrespondent.value.map((item) => item.count)));

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    data.value = await getDashboard();
  } catch (err: any) {
    error.value = err?.message ?? 'Failed to load dashboard';
  } finally {
    loading.value = false;
  }
};

onMounted(load);
</script>
