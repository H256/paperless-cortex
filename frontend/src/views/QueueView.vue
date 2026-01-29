<template>
  <section class="queue">
    <div class="queue__header">
      <h2>Queue Manager</h2>
      <div class="queue__actions">
        <button @click="refresh">Refresh</button>
        <button @click="clearQueue" :disabled="!queueStatus.enabled">Clear queue</button>
        <button @click="resetStats" :disabled="!queueStatus.enabled">Reset stats</button>
      </div>
    </div>

    <div class="queue__stats">
      <div>Status: {{ queueStatus.enabled ? 'enabled' : 'disabled' }}</div>
      <div>Length: {{ queueStatus.length ?? 'n/a' }}</div>
      <div>Total: {{ queueStatus.total ?? 0 }}</div>
      <div>In progress: {{ queueStatus.in_progress ?? 0 }}</div>
      <div>Done: {{ queueStatus.done ?? 0 }}</div>
    </div>

    <div class="queue__peek">
      <div class="queue__peek__header">
        <h3>Next items</h3>
        <label>
          Limit
          <input type="number" min="1" max="200" v-model.number="peekLimit" />
        </label>
        <button @click="loadPeek" :disabled="!queueStatus.enabled">Load</button>
      </div>
      <div v-if="peekError" class="queue__error">{{ peekError }}</div>
      <div v-else-if="peekItems.length === 0">
        <em>No items.</em>
      </div>
      <ul v-else class="queue__list">
        <li v-for="(item, index) in peekItems" :key="index">
          <span v-if="item.doc_id">Doc {{ item.doc_id }} · {{ item.task || 'full' }}</span>
          <span v-else>{{ item.raw || 'unknown' }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '../api';

const queueStatus = ref<{ enabled: boolean; length: number | null; total?: number; in_progress?: number; done?: number }>({
  enabled: false,
  length: null,
});
const peekItems = ref<Array<{ doc_id?: number; task?: string; raw?: string }>>([]);
const peekLimit = ref(20);
const peekError = ref('');

const refresh = async () => {
  try {
    const { data } = await api.get('/queue/status');
    queueStatus.value = data;
  } catch {
    queueStatus.value = { enabled: false, length: null };
  }
};

const loadPeek = async () => {
  peekError.value = '';
  try {
    const { data } = await api.get<{ items: Array<{ doc_id?: number; task?: string; raw?: string }> }>('/queue/peek', {
      params: { limit: peekLimit.value },
    });
    peekItems.value = data.items ?? [];
  } catch (err: any) {
    peekError.value = err?.message ?? 'Failed to load queue items';
  }
};

const clearQueue = async () => {
  await api.post('/queue/clear');
  await refresh();
  await loadPeek();
};

const resetStats = async () => {
  await api.post('/queue/reset-stats');
  await refresh();
};

onMounted(async () => {
  await refresh();
  await loadPeek();
});
</script>

<style scoped>
.queue__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.queue__actions {
  display: flex;
  gap: 8px;
}
.queue__stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  color: #475569;
}
.queue__peek {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 12px;
}
.queue__peek__header {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}
.queue__error {
  color: #b91c1c;
}
.queue__list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.queue__list li {
  padding: 4px 0;
  border-bottom: 1px solid #e2e8f0;
}
</style>
