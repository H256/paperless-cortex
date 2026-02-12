import { defineStore } from 'pinia'
import {
  getEmbedStatus,
  getStats,
  getSyncStatus,
  syncDocuments,
} from '../services/documents'
import type {
  DocumentStats,
  SyncStatus,
  EmbedStatus,
} from '../services/documents'

export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    syncing: false,
    embedding: false,
    lastSynced: null as string | null,
    incremental: true,
    pageOnly: false,
    syncStatus: {
      status: 'idle',
      processed: 0,
      total: 0,
      started_at: null,
      eta_seconds: null,
    } as SyncStatus,
    embedStatus: {
      status: 'idle',
      processed: 0,
      total: 0,
      started_at: null,
      eta_seconds: null,
    } as EmbedStatus,
    stats: {
      total: 0,
      processed: 0,
      unprocessed: 0,
      embeddings: 0,
      vision: 0,
      suggestions: 0,
      fully_processed: 0,
    } as DocumentStats,
  }),
  actions: {
    setSyncStatus(status: SyncStatus) {
      this.syncStatus = status
      this.lastSynced = status.last_synced_at ?? this.lastSynced
    },
    setEmbedStatus(status: EmbedStatus) {
      this.embedStatus = status
    },
    setStats(stats: DocumentStats) {
      this.stats = stats
    },
    async fetchStats() {
      try {
        this.stats = await getStats()
      } catch {
        this.stats = {
          total: 0,
          processed: 0,
          unprocessed: 0,
          embeddings: 0,
          vision: 0,
          suggestions: 0,
          fully_processed: 0,
        }
      }
    },
    async fetchSyncStatus() {
      try {
        this.syncStatus = await getSyncStatus()
        this.lastSynced = this.syncStatus.last_synced_at ?? null
      } catch {
        this.syncStatus = {
          status: 'idle',
          processed: 0,
          total: 0,
          started_at: null,
          eta_seconds: null,
        }
      }
    },
    async fetchEmbedStatus() {
      try {
        this.embedStatus = await getEmbedStatus()
      } catch {
        this.embedStatus = {
          status: 'idle',
          processed: 0,
          total: 0,
          started_at: null,
          eta_seconds: null,
        }
      }
    },
    async sync() {
      this.syncing = true
      try {
        await syncDocuments({
          page_size: 200,
          incremental: this.incremental,
          page: 1,
          page_only: this.pageOnly,
        })
        await this.fetchSyncStatus()
      } finally {
        this.syncing = false
      }
    },
  },
})
