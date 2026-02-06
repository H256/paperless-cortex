<template>
  <div class="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <header
      class="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80"
    >
      <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div>
          <h1 class="text-lg font-semibold tracking-tight">Paperless-NGX Cortex</h1>
          <p class="text-xs text-slate-500 dark:text-slate-400">Your documents, understood.</p>
        </div>
        <div class="flex items-center gap-4">
          <AppNav :items="navItems" />
          <div
            class="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400"
          >
            <span class="hidden sm:inline">Theme</span>
            <div
              class="flex items-center gap-1 rounded-full border border-slate-200 bg-white p-1 shadow-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold transition"
                :class="
                  theme === 'light'
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                "
                @click="theme = 'light'"
                aria-label="Light theme"
              >
                <Sun class="h-4 w-4" />
                <span class="hidden sm:inline">Light</span>
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold transition"
                :class="
                  theme === 'system'
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                "
                @click="theme = 'system'"
                aria-label="System theme"
              >
                <Laptop class="h-4 w-4" />
                <span class="hidden sm:inline">System</span>
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold transition"
                :class="
                  theme === 'dark'
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                "
                @click="theme = 'dark'"
                aria-label="Dark theme"
              >
                <Moon class="h-4 w-4" />
                <span class="hidden sm:inline">Dark</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-6 py-6">
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
          <div v-if="queueStore.status.enabled">Queue: {{ queueStore.status.length ?? 'n/a' }}</div>
          <div v-if="queueStore.status.enabled">Done: {{ queueStore.status.done ?? 0 }}</div>
          <div v-if="queueStore.status.enabled">Total: {{ queueStore.status.total ?? 0 }}</div>
          <div v-else>Queue: disabled</div>
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
import { ChartPie, FileText, Laptop, List, MessageCircle, Moon, Search, Sun, Wrench } from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, ref, watch, watchEffect } from 'vue'
import AppNav from './components/AppNav.vue'
import StatusLight from './components/StatusLight.vue'
import ToastHost from './components/ToastHost.vue'
import { useQueueStore } from './stores/queueStore'
import { useStatusStore } from './stores/statusStore'
import { useErrorStore } from './stores/errorStore'
import { useDocumentsStore } from './stores/documentsStore'

const queueStore = useQueueStore()
const statusStore = useStatusStore()
const errorStore = useErrorStore()
const documentsStore = useDocumentsStore()

const themeStorageKey = 'paperless_theme'
const storedTheme = window.localStorage?.getItem(themeStorageKey) || 'system'
const theme = ref(storedTheme)
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const prefersDark = ref(mediaQuery.matches)
const effectiveTheme = computed(() =>
  theme.value === 'system' ? (prefersDark.value ? 'dark' : 'light') : theme.value,
)
let statusStream: EventSource | null = null
let statusStreamRetryId: number | null = null
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: ChartPie },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/chat', label: 'Chat', icon: MessageCircle },
  { to: '/queue', label: 'Queue', icon: List },
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
  queueStore.refreshStatus()
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

const startStatusStream = () => {
  stopStatusStream()
  const url = `${apiBaseUrl}/status/stream`
  statusStream = new EventSource(url)
  statusStream.onmessage = (event) => {
    if (!event?.data) return
    try {
      const payload = JSON.parse(event.data)
      if (payload?.status) statusStore.applyStatus(payload.status)
      if (payload?.queue) queueStore.setStatus(payload.queue)
      if (payload?.sync) documentsStore.setSyncStatus(payload.sync)
      if (payload?.embeddings) documentsStore.setEmbedStatus(payload.embeddings)
    } catch {
      // ignore malformed payloads
    }
  }
  statusStream.onerror = () => {
    stopStatusStream()
    statusStreamRetryId = window.setTimeout(startStatusStream, 5000)
  }
}

const stopStatusStream = () => {
  if (statusStream) {
    statusStream.close()
    statusStream = null
  }
  if (statusStreamRetryId !== null) {
    window.clearTimeout(statusStreamRetryId)
    statusStreamRetryId = null
  }
}
</script>
