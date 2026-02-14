import { computed, ref } from 'vue'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  createWritebackJob,
  deleteWritebackJob,
  executePendingWritebackJobs,
  executeWritebackJob,
  getWritebackDryRunPreview,
  listWritebackHistory,
  listWritebackJobs,
  runWritebackDryRun,
  type WritebackDryRunItem,
  type WritebackJobSummary,
} from '../services/writeback'

export const useWritebackManager = () => {
  const queryClient = useQueryClient()
  const onlyChanged = ref(true)
  const selectedSet = ref<Set<number>>(new Set())
  const lastExecuteAllResults = ref<
    Array<{
      job_id: number
      status: string
      dry_run: boolean
      docs_selected: number
      docs_changed: number
      calls_count: number
      doc_ids: number[]
      error?: string | null
    }>
  >([])

  const previewQuery = useQuery({
    queryKey: computed(() => ['writeback-preview', onlyChanged.value]),
    queryFn: () =>
      getWritebackDryRunPreview({
        page: 1,
        page_size: 100,
        only_changed: onlyChanged.value,
      }),
    placeholderData: keepPreviousData,
  })

  const jobsQuery = useQuery({
    queryKey: ['writeback-jobs'],
    queryFn: () => listWritebackJobs(150),
    placeholderData: keepPreviousData,
  })

  const historyQuery = useQuery({
    queryKey: ['writeback-history'],
    queryFn: () => listWritebackHistory(150),
    placeholderData: keepPreviousData,
  })

  const selectedIds = computed(() => Array.from(selectedSet.value))
  const previewItems = computed<WritebackDryRunItem[]>(() => previewQuery.data.value?.items || [])
  const jobs = computed<WritebackJobSummary[]>(() => jobsQuery.data.value?.items || [])
  const historyItems = computed<WritebackJobSummary[]>(() => historyQuery.data.value?.items || [])
  const pendingCount = computed(() => jobs.value.filter((job) => job.status === 'pending').length)

  const selectAllChanged = () => {
    selectedSet.value = new Set(previewItems.value.filter((item) => item.changed).map((item) => item.doc_id))
  }

  const clearSelection = () => {
    selectedSet.value = new Set()
  }

  const toggleSelect = (docId: number) => {
    const next = new Set(selectedSet.value)
    if (next.has(docId)) next.delete(docId)
    else next.add(docId)
    selectedSet.value = next
  }

  const removeDocsFromSelection = (docIds: number[]) => {
    if (!docIds.length) return
    const idSet = new Set(docIds.map((v) => Number(v)))
    selectedSet.value = new Set(
      Array.from(selectedSet.value).filter((docId) => !idSet.has(Number(docId))),
    )
  }

  const reloadPreview = async () => {
    const result = await previewQuery.refetch()
    if (result.data) selectAllChanged()
    return result.data
  }

  const reloadJobs = () => jobsQuery.refetch()
  const reloadHistory = () => historyQuery.refetch()

  const runDryRunMutation = useMutation({
    mutationFn: (docIds: number[]) => runWritebackDryRun(docIds),
  })

  const enqueueMutation = useMutation({
    mutationFn: (docIds: number[]) => createWritebackJob(docIds),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['writeback-jobs'] })
    },
  })

  const executeJobMutation = useMutation({
    mutationFn: ({ jobId, dryRun }: { jobId: number; dryRun: boolean }) =>
      executeWritebackJob(jobId, dryRun),
    onSuccess: async (job, payload) => {
      if (!payload.dryRun && job.status === 'completed') {
        removeDocsFromSelection(job.doc_ids || [])
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['writeback-jobs'] }),
        queryClient.invalidateQueries({ queryKey: ['writeback-history'] }),
      ])
    },
  })

  const executeAllMutation = useMutation({
    mutationFn: ({ dryRun, limit }: { dryRun: boolean; limit: number }) =>
      executePendingWritebackJobs(dryRun, limit),
    onSuccess: async (result, payload) => {
      lastExecuteAllResults.value = (result.results || []).map((entry) => ({
        job_id: entry.job_id,
        status: entry.status,
        dry_run: entry.dry_run,
        docs_selected: entry.docs_selected,
        docs_changed: entry.docs_changed,
        calls_count: entry.calls_count,
        doc_ids: entry.doc_ids || [],
        error: entry.error,
      }))
      if (!payload.dryRun && (result.completed || 0) > 0) {
        removeDocsFromSelection(result.doc_ids || [])
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['writeback-jobs'] }),
        queryClient.invalidateQueries({ queryKey: ['writeback-history'] }),
      ])
    },
    onError: () => {
      lastExecuteAllResults.value = []
    },
  })

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: number) => deleteWritebackJob(jobId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['writeback-jobs'] }),
        queryClient.invalidateQueries({ queryKey: ['writeback-history'] }),
      ])
    },
  })

  return {
    onlyChanged,
    selectedSet,
    selectedIds,
    previewItems,
    jobs,
    historyItems,
    pendingCount,
    lastExecuteAllResults,
    previewQuery,
    jobsQuery,
    historyQuery,
    runDryRunMutation,
    enqueueMutation,
    executeJobMutation,
    executeAllMutation,
    deleteJobMutation,
    toggleSelect,
    selectAllChanged,
    clearSelection,
    reloadPreview,
    reloadJobs,
    reloadHistory,
  }
}
