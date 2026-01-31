<template>
  <section class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-100">PDF Viewer</h3>
        <p class="text-xs text-slate-500 dark:text-slate-400">Page {{ displayPage }} of {{ pageCount || '...' }}</p>
      </div>
      <div class="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
        <button
          class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="!pageCount || displayPage <= 1"
          @click="changePage(displayPage - 1)"
        >
          Prev
        </button>
        <input
          class="h-8 w-16 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          type="number"
          min="1"
          :max="pageCount || undefined"
          v-model.number="pageInput"
          @change="applyPageInput"
        />
        <button
          class="rounded-md border border-slate-200 bg-white px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
          :disabled="!pageCount || displayPage >= pageCount"
          @click="changePage(displayPage + 1)"
        >
          Next
        </button>
        <button
          class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-slate-500"
          @click="fitToWidth"
        >
          Fit
        </button>
      </div>
    </div>

    <div ref="containerRef" class="relative mt-4 w-full overflow-auto rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950">
      <div v-if="usePreviewFallback && previewBaseUrl" class="relative">
        <img
          ref="previewImgRef"
          class="block w-full rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
          :src="`${previewBaseUrl}?page=${displayPage}&max_dim=1400`"
          :alt="`Preview page ${displayPage}`"
          @load="onPreviewLoad"
        />
        <div
          v-if="highlightRects.length"
          class="pointer-events-none absolute inset-0"
          :style="{ width: `${viewportWidth || 1}px`, height: `${viewportHeight || 1}px` }"
        >
          <div
            v-for="(rect, idx) in highlightRects"
            :key="`hl-${idx}`"
            class="absolute rounded-sm border border-amber-400 bg-amber-200/50 shadow-sm"
            :style="{
              left: `${rect.left}px`,
              top: `${rect.top}px`,
              width: `${rect.width}px`,
              height: `${rect.height}px`,
            }"
          ></div>
        </div>
        <div v-if="error" class="absolute inset-x-0 bottom-2 text-center text-[11px] text-rose-600 dark:text-rose-300">
          {{ error }} - Showing preview
        </div>
      </div>
      <div v-else-if="error" class="flex items-center justify-center p-6 text-sm text-rose-600 dark:text-rose-300">
        {{ error }}
      </div>
      <div v-else class="relative">
        <canvas ref="canvasRef" class="block w-full"></canvas>
        <div
          v-if="highlightRects.length"
          class="pointer-events-none absolute inset-0"
          :style="{ width: `${viewportWidth}px`, height: `${viewportHeight}px` }"
        >
          <div
            v-for="(rect, idx) in highlightRects"
            :key="`hl-${idx}`"
            class="absolute rounded-sm border border-amber-400 bg-amber-200/50 shadow-sm"
            :style="{
              left: `${rect.left}px`,
              top: `${rect.top}px`,
              width: `${rect.width}px`,
              height: `${rect.height}px`,
            }"
          ></div>
        </div>
      </div>
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center text-xs text-slate-500 dark:text-slate-400">
        Loading PDF...
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { GlobalWorkerOptions, getDocument, PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist/legacy/build/pdf';
import pdfWorkerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.js?url';

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

type BBox = [number, number, number, number];

const props = defineProps<{
  pdfUrl: string;
  page?: number;
  highlights?: BBox[] | null;
  previewBaseUrl?: string;
}>();

const emit = defineEmits<{
  (e: 'update:page', value: number): void;
  (e: 'loaded', pageCount: number): void;
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);
const previewImgRef = ref<HTMLImageElement | null>(null);
const pdfDoc = ref<PDFDocumentProxy | null>(null);
const pageCount = ref(0);
const loading = ref(false);
const error = ref('');
const usePreviewFallback = ref(false);
const viewportWidth = ref(0);
const viewportHeight = ref(0);
const pageInput = ref(1);
let resizeObserver: ResizeObserver | null = null;

const displayPage = computed(() => {
  if (props.page && props.page > 0) return props.page;
  return 1;
});

const normalizedHighlights = computed(() => {
  if (!props.highlights || props.highlights.length === 0) return [];
  return props.highlights.filter((b) => Array.isArray(b) && b.length === 4);
});

const highlightRects = computed(() => {
  if (!viewportWidth.value || !viewportHeight.value) return [];
  return normalizedHighlights.value.map((bbox) => {
    const [x0, y0, x1, y1] = bbox;
    return {
      left: Math.max(0, x0 * viewportWidth.value),
      top: Math.max(0, y0 * viewportHeight.value),
      width: Math.max(4, (x1 - x0) * viewportWidth.value),
      height: Math.max(4, (y1 - y0) * viewportHeight.value),
    };
  });
});

const applyPageInput = () => {
  const next = Math.max(1, Math.min(pageCount.value || 1, pageInput.value || 1));
  changePage(next);
};

const changePage = (value: number) => {
  emit('update:page', value);
  pageInput.value = value;
};

const fitToWidth = () => {
  if (!pdfDoc.value) return;
  renderPage(displayPage.value);
};

const onPreviewLoad = () => {
  if (!previewImgRef.value) return;
  const rect = previewImgRef.value.getBoundingClientRect();
  viewportWidth.value = rect.width;
  viewportHeight.value = rect.height;
};

const loadPdf = async () => {
  if (!props.pdfUrl) return;
  loading.value = true;
  error.value = '';
  usePreviewFallback.value = false;
  try {
    const task = getDocument({
      url: props.pdfUrl,
      isEvalSupported: false,
      disableFontFace: true,
      disableWorker: true,
    });
    pdfDoc.value = await task.promise;
    pageCount.value = pdfDoc.value.numPages;
    emit('loaded', pageCount.value);
    pageInput.value = displayPage.value;
    await renderPage(displayPage.value);
  } catch (err: any) {
    error.value = err?.message ?? 'Failed to load PDF.';
    usePreviewFallback.value = Boolean(props.previewBaseUrl);
  } finally {
    loading.value = false;
  }
};

const renderPage = async (pageNumber: number) => {
  if (!pdfDoc.value) return;
  const canvas = canvasRef.value;
  const container = containerRef.value;
  if (!canvas || !container) return;
  let page: PDFPageProxy;
  try {
    page = await pdfDoc.value.getPage(pageNumber);
  } catch (err: any) {
    error.value = err?.message ?? 'Failed to render page.';
    usePreviewFallback.value = Boolean(props.previewBaseUrl);
    return;
  }
  const baseViewport = page.getViewport({ scale: 1 });
  const maxWidth = Math.max(320, container.clientWidth - 16);
  const scale = Math.min(2.5, maxWidth / baseViewport.width);
  const viewport = page.getViewport({ scale });
  viewportWidth.value = viewport.width;
  viewportHeight.value = viewport.height;
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  await page.render({ canvasContext: ctx, viewport }).promise;
};

onMounted(() => {
  loadPdf();
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      renderPage(displayPage.value);
    });
    resizeObserver.observe(containerRef.value);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
});

watch(
  () => props.pdfUrl,
  async (next, prev) => {
    if (next && next !== prev) {
      await loadPdf();
    }
  },
);

watch(
  () => displayPage.value,
  async (next) => {
    pageInput.value = next;
    await renderPage(next);
  },
);
</script>
