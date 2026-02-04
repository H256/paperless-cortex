import { defineStore } from 'pinia'
import { fetchHealthStatus, type HealthStatus } from '../services/status'

export const useStatusStore = defineStore('status', {
  state: () => ({
    health: {
      web: 'DOWN',
      worker: 'DOWN',
      llm: 'DOWN',
      llm_text: 'DOWN',
      llm_embedding: 'DOWN',
      llm_vision: 'DOWN',
      web_detail: 'unknown',
      worker_detail: 'unknown',
      llm_detail: 'unknown',
      llm_text_detail: 'unknown',
      llm_embedding_detail: 'unknown',
      llm_vision_detail: 'unknown',
    },
    paperlessBaseUrl: import.meta.env.VITE_PAPERLESS_BASE_URL || '',
    runtime: {
      paperless_base_url: '',
      llm_base_url: '',
      qdrant_url: '',
      redis_host: '',
      text_model: '',
      embedding_model: '',
      vision_model: '',
    },
  }),
  actions: {
    async refresh() {
      try {
        const data: HealthStatus = await fetchHealthStatus()
        this.health = {
          web: data.web?.status ?? 'DOWN',
          worker: data.worker?.status ?? 'DOWN',
          llm: data.llm?.status ?? 'DOWN',
          llm_text: data.llm_text?.status ?? 'DOWN',
          llm_embedding: data.llm_embedding?.status ?? 'DOWN',
          llm_vision: data.llm_vision?.status ?? 'DOWN',
          web_detail: data.web?.detail ?? 'ok',
          worker_detail: data.worker?.detail ?? 'unknown',
          llm_detail: data.llm?.detail ?? 'unknown',
          llm_text_detail: data.llm_text?.detail ?? 'unknown',
          llm_embedding_detail: data.llm_embedding?.detail ?? 'unknown',
          llm_vision_detail: data.llm_vision?.detail ?? 'unknown',
        }
        this.paperlessBaseUrl = data.paperless_base_url || this.paperlessBaseUrl
        this.runtime = {
          paperless_base_url: data.paperless_base_url || '',
          llm_base_url: data.llm_base_url || '',
          qdrant_url: data.qdrant_url || '',
          redis_host: data.redis_host || '',
          text_model: data.text_model || '',
          embedding_model: data.embedding_model || '',
          vision_model: data.vision_model || '',
        }
      } catch {
        this.health = {
          web: 'DOWN',
          worker: 'DOWN',
          llm: 'DOWN',
          llm_text: 'DOWN',
          llm_embedding: 'DOWN',
          llm_vision: 'DOWN',
          web_detail: 'unreachable',
          worker_detail: 'unreachable',
          llm_detail: 'unreachable',
          llm_text_detail: 'unreachable',
          llm_embedding_detail: 'unreachable',
          llm_vision_detail: 'unreachable',
        }
      }
    },
  },
})
