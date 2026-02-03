import { unwrap } from '../api/orval'
import { statusStatusGet } from '../api/generated/client'
import type { StatusResponse } from '@/api/generated/model'

export type HealthStatus = StatusResponse

export const fetchHealthStatus = () => unwrap<HealthStatus>(statusStatusGet())

