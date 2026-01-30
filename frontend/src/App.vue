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
              <FileText class="h-4 w-4" />
              Documents
            </span>
          </RouterLink>
          <RouterLink to="/search" v-slot="{ isActive }">
            <span :class="['inline-flex items-center gap-2 rounded-full px-3 py-1', isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:text-slate-900']">
              <Search class="h-4 w-4" />
              Search
            </span>
          </RouterLink>
          <RouterLink to="/queue" v-slot="{ isActive }">
            <span :class="['inline-flex items-center gap-2 rounded-full px-3 py-1', isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:text-slate-900']">
              <List class="h-4 w-4" />
              Queue
            </span>
          </RouterLink>
          <RouterLink to="/chat" v-slot="{ isActive }">
            <span :class="['inline-flex items-center gap-2 rounded-full px-3 py-1', isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:text-slate-900']">
              <MessageCircle class="h-4 w-4" />
              Chat
            </span>
          </RouterLink>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-6 py-6">
      <RouterView />
    </main>
    <footer class="border-t border-slate-200 bg-white">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-3 text-xs text-slate-500">
        <div class="flex flex-wrap items-center gap-4">
          <StatusLight label="Web" :status="statusStore.health.web" :title="statusStore.health.web_detail" />
          <StatusLight label="Worker" :status="statusStore.health.worker" :title="statusStore.health.worker_detail" />
          <StatusLight label="Ollama" :status="statusStore.health.ollama" :title="statusStore.health.ollama_detail" />
        </div>
        <div class="flex flex-wrap items-center gap-4">
          <div v-if="queueStore.status.enabled">Queue: {{ queueStore.status.length ?? 'n/a' }}</div>
          <div v-if="queueStore.status.enabled">Done: {{ queueStore.status.done ?? 0 }}</div>
          <div v-if="queueStore.status.enabled">Total: {{ queueStore.status.total ?? 0 }}</div>
          <div v-else>Queue: disabled</div>
        </div>
      </div>
    </footer>
    <div class="fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-2">
      <div
        v-for="err in errorStore.errors"
        :key="err.id"
        class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-md"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="font-semibold">Error</div>
            <div class="mt-1">{{ err.message }}</div>
            <div v-if="err.detail" class="mt-1 text-xs text-rose-600">{{ err.detail }}</div>
          </div>
          <button class="text-rose-400 hover:text-rose-600" @click="errorStore.remove(err.id)">×</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FileText, List, MessageCircle, Search } from 'lucide-vue-next';
import { onMounted, onUnmounted } from 'vue';
import StatusLight from './components/StatusLight.vue';
import { useQueueStore } from './stores/queueStore';
import { useStatusStore } from './stores/statusStore';
import { useErrorStore } from './stores/errorStore';

const queueStore = useQueueStore();
const statusStore = useStatusStore();
const errorStore = useErrorStore();

const onErrorEvent = (event: Event) => {
  const detail = (event as CustomEvent).detail || {};
  const message = detail.message || 'Unexpected error';
  const status = detail.status ? `(${detail.status})` : '';
  const combined = status ? `${message} ${status}` : message;
  errorStore.add(combined, detail.detail);
};

onMounted(() => {
  queueStore.refreshStatus();
  statusStore.refresh();
  setInterval(queueStore.refreshStatus, 5000);
  setInterval(statusStore.refresh, 7000);
  window.addEventListener('app-error', onErrorEvent as EventListener);
});

onUnmounted(() => {
  window.removeEventListener('app-error', onErrorEvent as EventListener);
});
</script>
