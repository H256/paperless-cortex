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
    runtime: {
      paperless_base_url: '',
      ollama_base_url: '',
      qdrant_url: '',
      redis_host: '',
      ollama_model: '',
      embedding_model: '',
      vision_model: '',
    },
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
        this.runtime = {
          paperless_base_url: data.paperless_base_url || '',
          ollama_base_url: data.ollama_base_url || '',
          qdrant_url: data.qdrant_url || '',
          redis_host: data.redis_host || '',
          ollama_model: data.ollama_model || '',
          embedding_model: data.embedding_model || '',
          vision_model: data.vision_model || '',
        };
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
