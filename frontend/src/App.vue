<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div>
          <h1 class="text-lg font-semibold tracking-tight">Paperless Intelligence</h1>
          <p class="text-xs text-slate-500">Arcane · read-only intelligence layer</p>
        </div>
        <nav class="flex items-center gap-4 text-sm font-medium">
          <RouterLink class="text-slate-600 hover:text-slate-900" to="/documents">Documents</RouterLink>
          <RouterLink class="text-slate-600 hover:text-slate-900" to="/connections">Connections</RouterLink>
          <RouterLink class="text-slate-600 hover:text-slate-900" to="/queue">Queue</RouterLink>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-6 py-6">
      <RouterView />
    </main>
    <footer class="border-t border-slate-200 bg-white">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-6 py-3 text-xs text-slate-500">
        <div v-if="queueStatus.enabled">Queue: {{ queueStatus.length ?? 'n/a' }}</div>
        <div v-if="queueStatus.enabled">In progress: {{ queueStatus.in_progress ?? 0 }}</div>
        <div v-if="queueStatus.enabled">Done: {{ queueStatus.done ?? 0 }}</div>
        <div v-if="queueStatus.enabled">Total: {{ queueStatus.total ?? 0 }}</div>
        <div v-else>Queue: disabled</div>
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

onMounted(() => {
  fetchQueueStatus();
  setInterval(fetchQueueStatus, 5000);
});
</script>
