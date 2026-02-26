<template>
  <div class="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <header
      class="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80"
    >
      <div class="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 md:flex-row md:items-center md:justify-between md:py-4">
        <div>
          <h1 class="text-lg font-semibold tracking-tight">Paperless-NGX Cortex</h1>
          <p class="text-xs text-slate-500 dark:text-slate-400">Your documents, understood.</p>
        </div>
        <div class="flex w-full flex-wrap items-center justify-end gap-2 md:w-auto md:gap-4">
          <AppNav :primary-items="primaryNavItems" :secondary-items="secondaryNavItems" />
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition hover:opacity-90"
            :class="processingBadgeClass"
            :title="processingBadgeTitle"
            @click="openProcessingActivity"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-current" :class="isProcessingActive ? 'animate-pulse' : ''" />
            {{ processingBadgeLabel }}
          </button>
          <div class="flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <div
              class="flex items-center gap-1 rounded-full border border-slate-200 bg-white p-1 shadow-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-1.5 py-1 text-xs font-semibold transition sm:px-2"
                :class="
                  theme === 'light'
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                "
                @click="theme = 'light'"
                aria-label="Light theme"
                title="Light"
              >
                <Sun class="h-4 w-4" />
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-1.5 py-1 text-xs font-semibold transition sm:px-2"
                :class="
                  theme === 'system'
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                "
                @click="theme = 'system'"
                aria-label="System theme"
                title="System"
              >
                <Laptop class="h-4 w-4" />
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-1.5 py-1 text-xs font-semibold transition sm:px-2"
                :class="
                  theme === 'dark'
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                "
                @click="theme = 'dark'"
                aria-label="Dark theme"
                title="Dark"
              >
                <Moon class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <RouterView />
    </main>
    <footer class="border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div
        class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-3 text-xs text-slate-500 dark:text-slate-400"
      >
        <div class="flex flex-wrap items-center gap-4">
          <StatusLight
            label="Web"
            :status="statusStore.health.web"
            :title="statusStore.health.web_detail"
          />
          <StatusLight
            label="Worker"
            :status="statusStore.health.worker"
            :title="statusStore.health.worker_detail"
          />
          <StatusLight
            label="LLM"
            :status="statusStore.health.llm"
            :title="statusStore.health.llm_detail"
          />
          <StatusLight
            label="LLM Text"
            :status="statusStore.health.llm_text"
            :title="statusStore.health.llm_text_detail"
          />
          <StatusLight
            label="LLM Embed"
            :status="statusStore.health.llm_embedding"
            :title="statusStore.health.llm_embedding_detail"
          />
          <StatusLight
            label="LLM Vision"
            :status="statusStore.health.llm_vision"
            :title="statusStore.health.llm_vision_detail"
          />
        </div>
        <div class="flex flex-wrap items-center gap-4">
          <div v-if="queueStatus.enabled">Queue: {{ queueStatus.length ?? 'n/a' }}</div>
          <div v-if="queueStatus.enabled">Done: {{ queueStatus.done ?? 0 }}</div>
          <div v-if="queueStatus.enabled">Total: {{ queueStatus.total ?? 0 }}</div>
          <div v-else>Queue: disabled</div>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <div>UI: {{ runtimeVersion.frontend }}</div>
          <div>API: {{ runtimeVersion.api }}</div>
          <div>App: {{ runtimeVersion.app }}</div>
        </div>
        <img
          src="/cortex_image_transparent.png"
          alt="Paperless-NGX Cortex"
          class="h-10 w-40 object-contain opacity-85"
        />
      </div>
    </footer>
    <ToastHost />
    <div class="fixed right-4 top-4 z-40 flex w-full max-w-sm flex-col gap-2">
      <div
        v-for="err in errorStore.errors"
        :key="err.id"
        class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-md dark:border-rose-900/40 dark:bg-rose-950/40 dark:text-rose-200"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="font-semibold">Error</div>
            <div class="mt-1">{{ err.message }}</div>
            <div v-if="err.detail" class="mt-1 text-xs text-rose-600">{{ err.detail }}</div>
          </div>
          <button
            class="text-rose-400 hover:text-rose-600 dark:text-rose-300"
            @click="errorStore.remove(err.id)"
          >
            x
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChartPie, ClipboardCheck, FileText, Laptop, List, MessageCircle, Moon, Search, Sun, Wrench, FileSearch } from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, ref, watch, watchEffect } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import AppNav, { type NavItem } from './components/AppNav.vue'
import StatusLight from './components/StatusLight.vue'
import ToastHost from './components/ToastHost.vue'
import { useStatusStore } from './stores/statusStore'
import { useErrorStore } from './stores/errorStore'
import { FRONTEND_VERSION } from './generated/version'
import { fetchQueueStatus } from './services/queue'
import { getEmbedStatus, getSyncStatus } from './services/documents'
import { useStatusStream } from './composables/useStatusStream'

const statusStore = useStatusStore()
const errorStore = useErrorStore()
const queryClient = useQueryClient()
const router = useRouter()
const queueStatusQuery = useQuery({
  queryKey: ['queue-status'],
  queryFn: () => fetchQueueStatus(),
  refetchInterval: 30_000,
  staleTime: 5_000,
})
const queueStatus = computed(() => queueStatusQuery.data.value ?? { enabled: false, length: null })
const runtimeVersion = computed(() => {
  const runtime = statusStore.runtime
  return {
    frontend: runtime.frontend_version || FRONTEND_VERSION,
    api: runtime.api_version || 'n/a',
    app: runtime.app_version || 'n/a',
  }
})
const syncStatusQuery = useQuery({
  queryKey: ['sync-status'],
  queryFn: () => getSyncStatus(),
  refetchInterval: 30_000,
  staleTime: 5_000,
})
const embedStatusQuery = useQuery({
  queryKey: ['embed-status'],
  queryFn: () => getEmbedStatus(),
  refetchInterval: 30_000,
  staleTime: 5_000,
})
const syncStatus = computed(() => syncStatusQuery.data.value ?? { status: 'idle', processed: 0, total: 0 })
const embedStatus = computed(() => embedStatusQuery.data.value ?? { status: 'idle', processed: 0, total: 0 })
const queueLength = computed(() => Number(queueStatus.value.length ?? 0))
const queueInProgress = computed(() => Number(queueStatus.value.in_progress ?? 0))
const syncRunning = computed(() => String(syncStatus.value.status || '').toLowerCase() === 'running')
const embeddingsRunning = computed(() => String(embedStatus.value.status || '').toLowerCase() === 'running')
const queueRunning = computed(() => Boolean(queueStatus.value.enabled) && (queueLength.value > 0 || queueInProgress.value > 0))
const isProcessingActive = computed(() => syncRunning.value || embeddingsRunning.value || queueRunning.value)
const processingBadgeLabel = computed(() => {
  if (syncRunning.value) {
    const processed = Number(syncStatus.value.processed ?? 0)
    const total = Number(syncStatus.value.total ?? 0)
    return `Sync ${processed}/${total || '?'}`
  }
  if (embeddingsRunning.value) {
    const processed = Number(embedStatus.value.processed ?? 0)
    const total = Number(embedStatus.value.total ?? 0)
    return `Embeddings ${processed}/${total || '?'}`
  }
  if (queueRunning.value) {
    return `Queue ${queueLength.value}`
  }
  return 'Idle'
})
const processingBadgeTitle = computed(() => {
  if (syncRunning.value) return 'Document sync is currently running. Click to open Queue.'
  if (embeddingsRunning.value) return 'Embedding processing is currently running. Click to open Queue.'
  if (queueRunning.value) return 'Queued background tasks are pending or running. Click to open Queue.'
  return 'No active background processing. Click to open Documents.'
})
const processingBadgeClass = computed(() =>
  isProcessingActive.value
    ? 'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200'
    : 'border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300',
)
const openProcessingActivity = () => {
  if (isProcessingActive.value) {
    router.push('/queue')
    return
  }
  router.push('/documents')
}

const themeStorageKey = 'paperless_theme'
const storedTheme = window.localStorage?.getItem(themeStorageKey) || 'system'
const theme = ref(storedTheme)
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const prefersDark = ref(mediaQuery.matches)
const effectiveTheme = computed(() =>
  theme.value === 'system' ? (prefersDark.value ? 'dark' : 'light') : theme.value,
)
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const { startStatusStream, stopStatusStream } = useStatusStream(apiBaseUrl, statusStore, queryClient)
const primaryNavItems: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: ChartPie },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/writeback', label: 'Writeback', icon: ClipboardCheck },
]

const secondaryNavItems: NavItem[] = [
  { to: '/chat', label: 'Chat', icon: MessageCircle },
  { to: '/queue', label: 'Queue', icon: List },
  { to: '/logs', label: 'Logs', icon: FileSearch },
  { to: '/operations', label: 'Operations', icon: Wrench },
]

const applyTheme = (value: string) => {
  const root = document.documentElement
  root.classList.toggle('dark', value === 'dark')
  root.style.colorScheme = value
}

const onMediaQueryChange = (event: MediaQueryListEvent) => {
  prefersDark.value = event.matches
}

const onErrorEvent = (event: Event) => {
  const detail = (event as CustomEvent).detail || {}
  const message = detail.message || 'Unexpected error'
  const status = detail.status ? `(${detail.status})` : ''
  const combined = status ? `${message} ${status}` : message
  errorStore.add(combined, detail.detail)
}

onMounted(() => {
  applyTheme(effectiveTheme.value)
  statusStore.refresh()
  startStatusStream()
  window.addEventListener('app-error', onErrorEvent as EventListener)
  mediaQuery.addEventListener('change', onMediaQueryChange)
})

onUnmounted(() => {
  window.removeEventListener('app-error', onErrorEvent as EventListener)
  mediaQuery.removeEventListener('change', onMediaQueryChange)
  stopStatusStream()
})

watch(theme, (value) => {
  window.localStorage?.setItem(themeStorageKey, value)
})

watchEffect(() => {
  applyTheme(effectiveTheme.value)
})
</script>
