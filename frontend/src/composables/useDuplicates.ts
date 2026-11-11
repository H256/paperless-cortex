import { ref } from 'vue'
import { unwrap } from '../api/orval'
import {
  getDuplicateGroupsDuplicatesGroupsGet,
  getIgnoredDuplicatesDuplicatesIgnoredGet,
  ignoreDuplicatePairDuplicatesIgnorePost,
  startDuplicateScanDuplicatesScanPost,
  unignoreDuplicatePairDuplicatesUnignorePost,
} from '../api/generated/client'
import type {
  DuplicateGroupOut,
  DuplicateGroupsResponse,
  DuplicateIgnoredResponse,
  DuplicateIgnoreResponse,
  DuplicatePairOut,
  DuplicateScanResponse,
} from '../api/generated/model'

export type DuplicateLevelFilter = 'check' | 'likely' | 'very_likely'

const errorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message || fallback
  if (typeof err === 'string') return err || fallback
  return fallback
}

export const useDuplicates = () => {
  const groups = ref<DuplicateGroupOut[]>([])
  const ignored = ref<DuplicatePairOut[]>([])
  const loading = ref(false)
  const scanning = ref(false)
  const error = ref('')
  let requestToken = 0

  const load = async (minLevel: DuplicateLevelFilter = 'check') => {
    const token = ++requestToken
    loading.value = true
    error.value = ''
    try {
      const [groupsResponse, ignoredResponse] = await Promise.all([
        unwrap<DuplicateGroupsResponse>(
          getDuplicateGroupsDuplicatesGroupsGet({ min_level: minLevel }),
        ),
        unwrap<DuplicateIgnoredResponse>(getIgnoredDuplicatesDuplicatesIgnoredGet()),
      ])
      if (token !== requestToken) return
      groups.value = groupsResponse?.groups ?? []
      ignored.value = ignoredResponse?.pairs ?? []
    } catch (err: unknown) {
      if (token !== requestToken) return
      error.value = errorMessage(err, 'Failed to load duplicates')
    } finally {
      if (token === requestToken) loading.value = false
    }
  }

  const startScan = async (): Promise<DuplicateScanResponse | null> => {
    scanning.value = true
    error.value = ''
    try {
      return await unwrap<DuplicateScanResponse>(startDuplicateScanDuplicatesScanPost())
    } catch (err: unknown) {
      error.value = errorMessage(err, 'Failed to start duplicate scan')
      return null
    } finally {
      scanning.value = false
    }
  }

  const setIgnored = async (
    pair: Pick<DuplicatePairOut, 'doc_a_id' | 'doc_b_id'>,
    value: boolean,
  ) => {
    error.value = ''
    const body = { doc_a_id: pair.doc_a_id, doc_b_id: pair.doc_b_id }
    try {
      await unwrap<DuplicateIgnoreResponse>(
        value
          ? ignoreDuplicatePairDuplicatesIgnorePost(body)
          : unignoreDuplicatePairDuplicatesUnignorePost(body),
      )
      return true
    } catch (err: unknown) {
      error.value = errorMessage(err, value ? 'Failed to ignore pair' : 'Failed to restore pair')
      return false
    }
  }

  return { groups, ignored, loading, scanning, error, load, startScan, setIgnored }
}
