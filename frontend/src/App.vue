<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div>
          <h1 class="text-lg font-semibold tracking-tight">Paperless Intelligence</h1>
          <p class="text-xs text-slate-500">Arcane · read-only intelligence layer</p>
        </div>
        <nav class="flex items-center gap-2 text-sm font-medium">
          <RouterLink to="/documents" v-slot="{ isActive }">
            <span :class="['inline-flex items-center gap-2 rounded-full px-3 py-1', isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:text-slate-900']">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M7 3h7l5 5v13H7z" />
                <path d="M14 3v5h5" />
              </svg>
              Documents
            </span>
          </RouterLink>
          <RouterLink to="/search" v-slot="{ isActive }">
            <span :class="['inline-flex items-center gap-2 rounded-full px-3 py-1', isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:text-slate-900']">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="7" />
                <line x1="16.65" y1="16.65" x2="21" y2="21" />
              </svg>
              Search
            </span>
          </RouterLink>
          <RouterLink to="/queue" v-slot="{ isActive }">
            <span :class="['inline-flex items-center gap-2 rounded-full px-3 py-1', isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:text-slate-900']">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 6h16" />
                <path d="M4 12h16" />
                <path d="M4 18h16" />
              </svg>
              Queue
            </span>
          </RouterLink>
          <span class="inline-flex items-center gap-2 rounded-full px-3 py-1 text-slate-400">
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a4 4 0 0 1-4 4H7l-4 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
            </svg>
            Chat
          </span>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-6 py-6">
      <RouterView />
    </main>
    <footer class="border-t border-slate-200 bg-white">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-3 text-xs text-slate-500">
        <div class="flex flex-wrap items-center gap-4">
          <div class="inline-flex items-center gap-2" :title="healthStatus.web_detail">
            <span :class="statusDot(healthStatus.web)"></span>
            Web
          </div>
          <div class="inline-flex items-center gap-2" :title="healthStatus.worker_detail">
            <span :class="statusDot(healthStatus.worker)"></span>
            Worker
          </div>
          <div class="inline-flex items-center gap-2" :title="healthStatus.ollama_detail">
            <span :class="statusDot(healthStatus.ollama)"></span>
            Ollama
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-4">
          <div v-if="queueStatus.enabled">Queue: {{ queueStatus.length ?? 'n/a' }}</div>
          <div v-if="queueStatus.enabled">Done: {{ queueStatus.done ?? 0 }}</div>
          <div v-if="queueStatus.enabled">Total: {{ queueStatus.total ?? 0 }}</div>
          <div v-else>Queue: disabled</div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from './api';

const queueStatus = ref<{ enabled: boolean; length: number | null; total?: number; in_progress?: number; done?: number }>({
  enabled: false,
  length: null,
});

const healthStatus = ref<{ web: string; worker: string; ollama: string; web_detail: string; worker_detail: string; ollama_detail: string }>({
  web: 'DOWN',
  worker: 'DOWN',
  ollama: 'DOWN',
  web_detail: 'unknown',
  worker_detail: 'unknown',
  ollama_detail: 'unknown',
});

const fetchQueueStatus = async () => {
  try {
    const { data } = await api.get<{ enabled: boolean; length: number | null; total?: number; in_progress?: number; done?: number }>(
      '/queue/status'
    );
    queueStatus.value = data;
  } catch {
    queueStatus.value = { enabled: false, length: null };
  }
};

const fetchHealth = async () => {
  try {
    const { data } = await api.get<{ web?: { status?: string; detail?: string }; worker?: { status?: string; detail?: string }; ollama?: { status?: string; detail?: string } }>('/status');
    healthStatus.value = {
      web: data.web?.status ?? 'DOWN',
      worker: data.worker?.status ?? 'DOWN',
      ollama: data.ollama?.status ?? 'DOWN',
      web_detail: data.web?.detail ?? 'ok',
      worker_detail: data.worker?.detail ?? 'unknown',
      ollama_detail: data.ollama?.detail ?? 'unknown',
    };
  } catch {
    healthStatus.value = {
      web: 'DOWN',
      worker: 'DOWN',
      ollama: 'DOWN',
      web_detail: 'unreachable',
      worker_detail: 'unreachable',
      ollama_detail: 'unreachable',
    };
  }
};

const statusDot = (status: string) =>
  `h-2 w-2 rounded-full ${status === 'UP' ? 'bg-emerald-500' : 'bg-rose-500'}`;

onMounted(() => {
  fetchQueueStatus();
  fetchHealth();
  setInterval(fetchQueueStatus, 5000);
  setInterval(fetchHealth, 7000);
});
</script>

