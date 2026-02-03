import { unwrap } from '../api/orval'
import { searchEmbeddingsSearchGet } from '../api/generated/client'
import type { EmbeddingSearchResponse, EmbeddingMatch } from '../api/generated/model'

export type SearchResult = EmbeddingMatch

export const searchEmbeddings = (params: {
  q: string
  top_k: number
  source?: string
  dedupe?: boolean
  rerank?: boolean
  min_quality?: number
}) => unwrap<EmbeddingSearchResponse>(searchEmbeddingsSearchGet(params))
