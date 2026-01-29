<template>
  <div class="app">
    <header class="app__header">
      <h1>Paperless Intelligence</h1>
      <nav class="app__nav">
        <RouterLink to="/documents">Documents</RouterLink>
        <RouterLink to="/connections">Connections</RouterLink>
        <RouterLink to="/queue">Queue</RouterLink>
      </nav>
    </header>
    <main class="app__main">
      <RouterView />
    </main>
    <footer class="app__footer">
      <div v-if="queueStatus.enabled">
        Queue: {{ queueStatus.length ?? 'n/a' }}
      </div>
      <div v-if="queueStatus.enabled">
        In progress: {{ queueStatus.in_progress ?? 0 }}
      </div>
      <div v-if="queueStatus.enabled">
        Done: {{ queueStatus.done ?? 0 }}
      </div>
      <div v-if="queueStatus.enabled">
        Total: {{ queueStatus.total ?? 0 }}
      </div>
      <div v-else>
        Queue: disabled
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from './api';

const queueStatus = ref<{ enabled: boolean; length: number | null }>({
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

<style scoped>
.app {
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  color: #1f2937;
  background: #f8fafc;
  min-height: 100vh;
}
.app__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e2e8f0;
}
.app__nav a {
  margin-left: 12px;
  color: #2563eb;
  text-decoration: none;
}
.app__main {
  padding: 24px;
}
.app__footer {
  padding: 12px 24px;
  background: white;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 12px;
  display: flex;
  gap: 12px;
}
</style>
