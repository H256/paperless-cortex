import { unwrap } from '../api/orval'
import { statusStatusGet, getQueueStatusQueueStatusGet } from '../api/generated/client'
import type { StatusResponse, QueueStatusResponse } from '@/api/generated/model'

export type HealthStatus = StatusResponse
export type QueueStatus = QueueStatusResponse

export const fetchHealthStatus = () => unwrap<HealthStatus>(statusStatusGet())

