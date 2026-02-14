import { unwrap } from '../api/orval'
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
  getDelayedQueueQueueDelayedGet,
  getDlqQueueDlqGet,
  clearDlqQueueDlqClearPost,
  requeueDlqQueueDlqRequeuePost,
  getRunningQueueRunningGet,
  getWorkerLockQueueWorkerLockGet,
  resetWorkerLockRouteQueueWorkerLockResetPost,
  getErrorTypesQueueErrorTypesGet,
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
  QueueDelayedItem,
  QueueDelayedResponse,
  QueueDlqItem,
  QueueDlqResponse,
  QueueDlqActionResponse,
  QueueRunningResponse,
  QueueWorkerLockStatusResponse,
  QueueWorkerLockResetResponse,
  ErrorTypeCatalogResponse,
  ResetWorkerLockRouteQueueWorkerLockResetPostParams,
} from '../api/generated/model'

export type QueueStatus = QueueStatusResponse
export type QueuePeekItem = QueuePeekItemModel
export type QueueWorkerLockStatus = QueueWorkerLockStatusResponse
export type QueueWorkerLockReset = QueueWorkerLockResetResponse
export type QueueRunningStatus = QueueRunningResponse
export type QueueTaskRun = TaskRunItem
export type QueueTaskRunList = TaskRunListResponse
export type QueueDelayedEntry = QueueDelayedItem
export type QueueDelayedList = QueueDelayedResponse
export type QueueDlqEntry = QueueDlqItem
export type QueueDlqList = QueueDlqResponse
export type QueueErrorTypeDetail = {
  code: string
  retryable: boolean
  category: string
  description: string
}
export type QueueErrorTypeCatalog = ErrorTypeCatalogResponse

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
  unwrap<QueueRunningStatus>(getRunningQueueRunningGet())

export const fetchQueueTaskRuns = (params?: GetTaskRunsQueueTaskRunsGetParams) =>
  unwrap<QueueTaskRunList>(getTaskRunsQueueTaskRunsGet(params))

export const fetchQueueDelayed = (limit = 100) =>
  unwrap<QueueDelayedResponse>(getDelayedQueueQueueDelayedGet({ limit }))

export const fetchQueueDlq = (limit = 100) =>
  unwrap<QueueDlqResponse>(getDlqQueueDlqGet({ limit }))

export const clearQueueDlq = () =>
  unwrap<QueueDlqActionResponse>(clearDlqQueueDlqClearPost())

export const requeueQueueDlqItem = (index: number) =>
  unwrap<QueueDlqActionResponse>(requeueDlqQueueDlqRequeuePost({ index }))

export const fetchWorkerLockStatus = () =>
  unwrap<QueueWorkerLockStatus>(getWorkerLockQueueWorkerLockGet())

export const resetWorkerLock = (force = false) =>
  unwrap<QueueWorkerLockReset>(
    resetWorkerLockRouteQueueWorkerLockResetPost({
      force,
    } as ResetWorkerLockRouteQueueWorkerLockResetPostParams),
  )

export const fetchQueueErrorTypes = () =>
  unwrap<QueueErrorTypeCatalog>(getErrorTypesQueueErrorTypesGet())
