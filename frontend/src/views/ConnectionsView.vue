<template>
  <section class="connections">
    <div class="connections__header">
      <h2>Connections</h2>
      <button @click="load">Reload</button>
    </div>
    <table class="connections__table">
      <thead>
        <tr>
          <th>Service</th>
          <th>Status</th>
          <th>Detail</th>
          <th>Latency (ms)</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.service">
          <td>{{ row.service }}</td>
          <td :class="row.status === 'UP' ? 'ok' : 'down'">{{ row.status }}</td>
          <td>{{ row.detail }}</td>
          <td>{{ row.latency_ms }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '../api';

interface ConnectionRow {
  service: string;
  status: string;
  detail: string;
  latency_ms: number;
}

const rows = ref<ConnectionRow[]>([]);

const load = async () => {
  const { data } = await api.get<ConnectionRow[]>('/connections');
  rows.value = data;
};

onMounted(load);
</script>

<style scoped>
.connections__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.connections__table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border: 1px solid #e2e8f0;
}
.connections__table th,
.connections__table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
}
.ok {
  color: #16a34a;
  font-weight: 600;
}
.down {
  color: #dc2626;
  font-weight: 600;
}
</style>
