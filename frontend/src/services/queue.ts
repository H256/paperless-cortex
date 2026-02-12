import { unwrap } from '../api/orval'
import { request } from './http'
import {
  getQueueStatusQueueStatusGet,
  peekQueuePeekGet,
  clearQueueClearPost,
  resetQueueResetStatsPost,
  pauseQueuePausePost,
  resumeQueueResumePost,
  moveQueueReorderPost,
  removeQueueRemovePost,
  moveTopQueueMoveTopPost,
  moveBottomQueueMoveBottomPost,
  getTaskRunsQueueTaskRunsGet,
} from '../api/generated/client'
import type {
  QueueStatusResponse,
  QueuePeekResponse,
  QueuePeekItem as QueuePeekItemModel,
  QueuePauseResponse,
  QueueMoveResponse,
  QueueRemoveResponse,
  QueueMoveRequest,
  QueueMoveEdgeRequest,
  QueueRemoveRequest,
  TaskRunItem,
  TaskRunListResponse,
  GetTaskRunsQueueTaskRunsGetParams,
} from '../api/generated/model'

export type QueueStatus = QueueStatusResponse
export type QueuePeekItem = QueuePeekItemModel
export type QueueWorkerLockStatus = {
  enabled: boolean
  has_lock: boolean
  owner?: string | null
  ttl_seconds?: number | null
}
export type QueueWorkerLockReset = {
  enabled: boolean
  reset: boolean
  had_lock: boolean
  reason?: string | null
}
export type QueueRunningStatus = {
  enabled: boolean
  task?: QueuePeekItem | null
  started_at?: number | null
}
export type QueueTaskRun = TaskRunItem
export type QueueTaskRunList = TaskRunListResponse

export const fetchQueueStatus = () => unwrap<QueueStatus>(getQueueStatusQueueStatusGet())

export const fetchQueuePeek = (limit: number) =>
  unwrap<QueuePeekResponse>(peekQueuePeekGet({ limit }))

export const clearQueue = () => unwrap<void>(clearQueueClearPost())

export const resetQueueStats = () => unwrap<void>(resetQueueResetStatsPost())

export const pauseQueue = () => unwrap<QueuePauseResponse>(pauseQueuePausePost())

export const resumeQueue = () => unwrap<QueuePauseResponse>(resumeQueueResumePost())

export const moveQueueItem = (payload: QueueMoveRequest) =>
  unwrap<QueueMoveResponse>(moveQueueReorderPost(payload))

export const removeQueueItem = (payload: QueueRemoveRequest) =>
  unwrap<QueueRemoveResponse>(removeQueueRemovePost(payload))

export const moveQueueItemTop = (payload: QueueMoveEdgeRequest) =>
  unwrap<QueueMoveResponse>(moveTopQueueMoveTopPost(payload))

export const moveQueueItemBottom = (payload: QueueMoveEdgeRequest) =>
  unwrap<QueueMoveResponse>(moveBottomQueueMoveBottomPost(payload))

export const fetchQueueRunning = () =>
  request<QueueRunningStatus>('/queue/running')

export const fetchQueueTaskRuns = (params?: GetTaskRunsQueueTaskRunsGetParams) =>
  unwrap<QueueTaskRunList>(getTaskRunsQueueTaskRunsGet(params))

export const fetchWorkerLockStatus = () =>
  request<QueueWorkerLockStatus>('/queue/worker-lock')

export const resetWorkerLock = (force = false) =>
  request<QueueWorkerLockReset>('/queue/worker-lock/reset', {
    method: 'POST',
    params: { force },
  })
