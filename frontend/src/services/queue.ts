import { unwrap } from '../api/orval';
import { request } from './http';
import {
  getQueueStatusQueueStatusGet,
  peekQueuePeekGet,
  clearQueueClearPost,
  resetQueueResetStatsPost,
  pauseQueuePausePost,
  resumeQueueResumePost,
  moveQueueReorderPost,
  removeQueueRemovePost,
} from '../api/generated/client';
import type {
  QueueStatusResponse,
  QueuePeekResponse,
  QueuePeekItem as QueuePeekItemModel,
  QueuePauseResponse,
  QueueMoveResponse,
  QueueRemoveResponse,
  QueueMoveRequest,
  QueueRemoveRequest,
} from '../api/generated/model';

export type QueueStatus = QueueStatusResponse;
export type QueuePeekItem = QueuePeekItemModel;

export const fetchQueueStatus = () => unwrap<QueueStatus>(getQueueStatusQueueStatusGet());

export const fetchQueuePeek = (limit: number) =>
  unwrap<QueuePeekResponse>(peekQueuePeekGet({ limit }));

export const clearQueue = () => unwrap<void>(clearQueueClearPost());

export const resetQueueStats = () => unwrap<void>(resetQueueResetStatsPost());

export const pauseQueue = () => unwrap<QueuePauseResponse>(pauseQueuePausePost());

export const resumeQueue = () => unwrap<QueuePauseResponse>(resumeQueueResumePost());

export const moveQueueItem = (payload: QueueMoveRequest) => unwrap<QueueMoveResponse>(moveQueueReorderPost(payload));

export const removeQueueItem = (payload: QueueRemoveRequest) =>
  unwrap<QueueRemoveResponse>(removeQueueRemovePost(payload));

export const moveQueueItemTop = (payload: { index: number }) =>
  request<QueueMoveResponse>('/queue/move-top', { method: 'POST', body: payload });

export const moveQueueItemBottom = (payload: { index: number }) =>
  request<QueueMoveResponse>('/queue/move-bottom', { method: 'POST', body: payload });
