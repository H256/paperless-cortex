import { defineStore } from 'pinia';
import { fetchHealthStatus, HealthStatus } from '../services/status';

export const useStatusStore = defineStore('status', {
  state: () => ({
    health: {
      web: 'DOWN',
      worker: 'DOWN',
      ollama: 'DOWN',
      web_detail: 'unknown',
      worker_detail: 'unknown',
      ollama_detail: 'unknown',
    },
    paperlessBaseUrl: import.meta.env.VITE_PAPERLESS_BASE_URL || '',
  }),
  actions: {
    async refresh() {
      try {
        const data: HealthStatus = await fetchHealthStatus();
        this.health = {
          web: data.web?.status ?? 'DOWN',
          worker: data.worker?.status ?? 'DOWN',
          ollama: data.ollama?.status ?? 'DOWN',
          web_detail: data.web?.detail ?? 'ok',
          worker_detail: data.worker?.detail ?? 'unknown',
          ollama_detail: data.ollama?.detail ?? 'unknown',
        };
        this.paperlessBaseUrl = data.paperless_base_url || this.paperlessBaseUrl;
      } catch {
        this.health = {
          web: 'DOWN',
          worker: 'DOWN',
          ollama: 'DOWN',
          web_detail: 'unreachable',
          worker_detail: 'unreachable',
          ollama_detail: 'unreachable',
        };
      }
    },
  },
});
