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
} from '../api/generated/model'

export type QueueStatus = QueueStatusResponse
export type QueuePeekItem = QueuePeekItemModel

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
