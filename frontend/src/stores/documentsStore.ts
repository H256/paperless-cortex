import { defineStore } from 'pinia'
import {
  cancelEmbeddings,
  cancelSync,
  getCorrespondents,
  getEmbedStatus,
  getStats,
  getSyncStatus,
  getTags,
  listDocuments,
  deleteEmbeddings,
  deleteSuggestions,
  deleteVisionOcr,
  clearIntelligence,
  processMissing,
  resetIntelligence,
  syncDocuments,
} from '../services/documents'
import type {
  DocumentRow,
  DocumentStats,
  SyncStatus,
  EmbedStatus,
  Tag,
  Correspondent,
  ProcessMissingParams,
} from '../services/documents'
import type { SyncDocumentsSyncDocumentsPostParams } from '@/api/generated/model'
import { toOptionalNumber } from '../utils/number'

export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    documents: [] as DocumentRow[],
    page: 1,
    pageSize: 20,
    ordering: '-date',
    totalCount: 0,
    tags: [] as Tag[],
    correspondents: [] as Correspondent[],
    selectedTag: '',
    selectedCorrespondent: '',
    selectedReviewStatus: 'all' as 'all' | 'unreviewed' | 'reviewed' | 'needs_review',
    dateFrom: '',
    dateTo: '',
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
    processPreview: null as null | {
      missing_docs?: number
      missing_vision_ocr?: number
      missing_embeddings?: number
      missing_embeddings_vision?: number
      missing_page_notes?: number
      missing_summary_hierarchical?: number
      missing_suggestions_paperless?: number
      missing_suggestions_vision?: number
      docs?: number
    },
    processPreviewLoading: false,
    processStartLoading: false,
    processStartResult: null as null | { enqueued?: number; tasks?: number },
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
    async load() {
      const {
        page,
        pageSize,
        ordering,
        selectedCorrespondent,
        selectedTag,
        selectedReviewStatus,
        dateFrom,
        dateTo,
      } =
        this
      const data = await listDocuments({
        page,
        page_size: pageSize,
        ordering,
        correspondent__id: toOptionalNumber(selectedCorrespondent),
        tags__id: toOptionalNumber(selectedTag),
        document_date__gte: dateFrom || undefined,
        document_date__lte: dateTo || undefined,
        include_derived: true,
        review_status: selectedReviewStatus,
      })
      this.documents = data.results ?? []
      this.totalCount = data.count ?? this.documents.length
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
    async fetchMeta() {
      const [tagsResp, corrResp] = await Promise.allSettled([getTags(), getCorrespondents()])
      if (tagsResp.status === 'fulfilled') {
        this.tags = tagsResp.value.results ?? []
      } else {
        this.tags = []
      }
      if (corrResp.status === 'fulfilled') {
        this.correspondents = corrResp.value.results ?? []
      } else {
        this.correspondents = []
      }
    },
    async sync() {
      this.syncing = true
      try {
        await syncDocuments({
          page_size: this.pageSize,
          incremental: this.incremental,
          page: this.page,
          page_only: this.pageOnly,
        })
        await this.fetchSyncStatus()
        await this.load()
      } finally {
        this.syncing = false
      }
    },
    async continueProcessingPreview(options?: ProcessMissingParams) {
      this.syncing = true
      this.processPreviewLoading = true
      this.processPreview = {}
      try {
        await syncDocuments({
          page_size: 200,
          incremental: false,
          page: 1,
          page_only: false,
          embed: false,
          force_embed: false,
          mark_missing: true,
          insert_only: true,
        })
        await this.refreshProcessPreview(options)
        await this.fetchSyncStatus()
        await this.fetchEmbedStatus()
        await this.load()
      } finally {
        this.syncing = false
        this.processPreviewLoading = false
      }
    },
    async refreshProcessPreview(options?: ProcessMissingParams) {
      this.processPreviewLoading = true
      try {
        const preview = await processMissing({ dry_run: true, ...options })
        this.processPreview = {
          docs: preview.docs ?? undefined,
          missing_docs: preview.missing_docs ?? undefined,
          missing_vision_ocr: preview.missing_vision_ocr ?? undefined,
          missing_embeddings: preview.missing_embeddings ?? undefined,
          missing_embeddings_vision: preview.missing_embeddings_vision ?? undefined,
          missing_page_notes: preview.missing_page_notes ?? undefined,
          missing_summary_hierarchical: preview.missing_summary_hierarchical ?? undefined,
          missing_suggestions_paperless: preview.missing_suggestions_paperless ?? undefined,
          missing_suggestions_vision: preview.missing_suggestions_vision ?? undefined,
        }
      } finally {
        this.processPreviewLoading = false
      }
    },
    async startProcessingFromPreview(options?: ProcessMissingParams) {
      this.syncing = true
      this.processStartLoading = true
      this.processStartResult = null
      try {
        const result = await processMissing(options)
        this.processStartResult = { enqueued: result.enqueued, tasks: result.tasks }
        await this.fetchSyncStatus()
        await this.fetchEmbedStatus()
        await this.load()
      } finally {
        this.syncing = false
        this.processStartLoading = false
      }
    },
    clearProcessPreview() {
      this.processPreview = null
      this.processStartResult = null
    },
    async reprocessAll() {
      this.syncing = true
      try {
        const params: SyncDocumentsSyncDocumentsPostParams = {
          page_size: 200,
          incremental: false,
          page: 1,
          page_only: false,
          embed: false,
          force_embed: false,
          mark_missing: true,
        }
        await syncDocuments(params)
        await resetIntelligence()
        await processMissing()
        await this.fetchSyncStatus()
        await this.fetchEmbedStatus()
        await this.load()
      } finally {
        this.syncing = false
      }
    },
    async removeVisionOcr() {
      return deleteVisionOcr()
    },
    async removeSuggestions() {
      return deleteSuggestions()
    },
    async removeEmbeddings() {
      return deleteEmbeddings()
    },
    async clearAllIntelligence() {
      return clearIntelligence()
    },
    async cancelProcessing() {
      await cancelSync()
      await cancelEmbeddings()
    },
  },
})
