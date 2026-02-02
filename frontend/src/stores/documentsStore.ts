import { defineStore } from 'pinia';
import {
  cancelEmbeddings,
  cancelSync,
  getCorrespondents,
  getEmbedStatus,
  getStats,
  getSyncStatus,
  getTags,
  ingestEmbeddings,
  ingestEmbeddingsForDocs,
  listDocuments,
  processMissing,
  resetIntelligence,
  syncDocuments,
  syncDocument,
} from '../services/documents';
import { DocumentRow, DocumentStats, SyncStatus, EmbedStatus, Tag, Correspondent, ProcessMissingParams } from '../services/documents';

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
      missing_docs?: number;
      missing_vision_ocr?: number;
      missing_embeddings?: number;
      missing_embeddings_vision?: number;
      missing_suggestions_paperless?: number;
      missing_suggestions_vision?: number;
      docs?: number;
    },
    processPreviewLoading: false,
    processStartLoading: false,
    processStartResult: null as null | { enqueued?: number; tasks?: number },
  }),
  actions: {
    async load() {
      const { page, pageSize, ordering, selectedCorrespondent, selectedTag, dateFrom, dateTo } = this;
      const data = await listDocuments({
        page,
        page_size: pageSize,
        ordering,
        correspondent__id: selectedCorrespondent || undefined,
        tags__id: selectedTag || undefined,
        document_date__gte: dateFrom || undefined,
        document_date__lte: dateTo || undefined,
        include_derived: true,
      });
      this.documents = data.results ?? [];
      this.totalCount = data.count ?? this.documents.length;
    },
    async fetchStats() {
      try {
        this.stats = await getStats();
      } catch {
        this.stats = {
          total: 0,
          processed: 0,
          unprocessed: 0,
          embeddings: 0,
          vision: 0,
          suggestions: 0,
          fully_processed: 0,
        };
      }
    },
    async fetchSyncStatus() {
      try {
        this.syncStatus = await getSyncStatus();
        this.lastSynced = this.syncStatus.last_synced_at ?? null;
      } catch {
        this.syncStatus = {
          status: 'idle',
          processed: 0,
          total: 0,
          started_at: null,
          eta_seconds: null,
        };
      }
    },
    async fetchEmbedStatus() {
      try {
        this.embedStatus = await getEmbedStatus();
      } catch {
        this.embedStatus = {
          status: 'idle',
          processed: 0,
          total: 0,
          started_at: null,
          eta_seconds: null,
        };
      }
    },
    async fetchMeta() {
      const [tagsResp, corrResp] = await Promise.all([getTags(), getCorrespondents()]);
      this.tags = tagsResp.results ?? [];
      this.correspondents = corrResp.results ?? [];
    },
    async sync() {
      this.syncing = true;
      try {
        await syncDocuments({
          page_size: this.pageSize,
          incremental: this.incremental,
          page: this.page,
          page_only: this.pageOnly,
        });
        await this.fetchSyncStatus();
        await this.load();
      } finally {
        this.syncing = false;
      }
    },
    async reprocessFiltered() {
      this.syncing = true;
      try {
        await syncDocuments({
          page_size: this.pageSize,
          incremental: false,
          page: 1,
          page_only: false,
          embed: true,
          force_embed: true,
        });
        await this.fetchSyncStatus();
        await this.fetchEmbedStatus();
        await this.load();
      } finally {
        this.syncing = false;
      }
    },
    async continueProcessingPreview(options?: ProcessMissingParams) {
      this.syncing = true;
      this.processPreviewLoading = true;
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
        });
        await this.refreshProcessPreview(options);
        await this.fetchSyncStatus();
        await this.fetchEmbedStatus();
        await this.load();
      } finally {
        this.syncing = false;
        this.processPreviewLoading = false;
      }
    },
    async refreshProcessPreview(options?: ProcessMissingParams) {
      this.processPreviewLoading = true;
      try {
        const preview = await processMissing({ dry_run: true, ...options });
        this.processPreview = {
          docs: preview.docs,
          missing_docs: preview.missing_docs,
          missing_vision_ocr: preview.missing_vision_ocr,
          missing_embeddings: preview.missing_embeddings,
          missing_embeddings_vision: preview.missing_embeddings_vision,
          missing_suggestions_paperless: preview.missing_suggestions_paperless,
          missing_suggestions_vision: preview.missing_suggestions_vision,
        };
      } finally {
        this.processPreviewLoading = false;
      }
    },
    async startProcessingFromPreview(options?: ProcessMissingParams) {
      this.syncing = true;
      this.processStartLoading = true;
      this.processStartResult = null;
      try {
        const result = await processMissing(options);
        this.processStartResult = { enqueued: result.enqueued, tasks: result.tasks };
        await this.fetchSyncStatus();
        await this.fetchEmbedStatus();
        await this.load();
      } finally {
        this.syncing = false;
        this.processStartLoading = false;
      }
    },
    clearProcessPreview() {
      this.processPreview = null;
      this.processStartResult = null;
    },
    async reprocessAll() {
      this.syncing = true;
      try {
        await syncDocuments({
          page_size: 200,
          incremental: false,
          page: 1,
          page_only: false,
          embed: false,
          force_embed: false,
          mark_missing: true,
        } as any);
        await resetIntelligence();
        await processMissing();
        await this.fetchSyncStatus();
        await this.fetchEmbedStatus();
        await this.load();
      } finally {
        this.syncing = false;
      }
    },
    async reembedFiltered(force = false) {
      this.embedding = true;
      try {
        const ids = this.documents.map((doc) => doc.id);
        if (ids.length) {
          await ingestEmbeddingsForDocs(ids, { force });
        } else {
          await ingestEmbeddings({ force, limit: 0 });
        }
        await this.fetchEmbedStatus();
      } finally {
        this.embedding = false;
      }
    },
    async reprocessMissing() {
      this.syncing = true;
      try {
        const missing = this.documents.filter((doc) => !doc.has_embeddings || !doc.has_vision_pages);
        for (const doc of missing) {
          await syncDocument(doc.id, { embed: true, force_embed: true });
        }
        await this.fetchEmbedStatus();
      } finally {
        this.syncing = false;
      }
    },
    async reprocessDocument(docId: number, doReembed: boolean) {
      await syncDocument(docId, { embed: doReembed, force_embed: doReembed });
    },
    async cancelProcessing() {
      await cancelSync();
      await cancelEmbeddings();
    },
  },
});
