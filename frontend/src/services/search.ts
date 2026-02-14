import { unwrap } from '../api/orval'
import { searchEmbeddingsSearchGet } from '../api/generated/client'
import type {
  EmbeddingSearchResponse,
  EmbeddingMatch,
  SearchEmbeddingsSearchGetParams,
} from '@/api/generated/model'

export type SearchResult = EmbeddingMatch

export const searchEmbeddings = (params: SearchEmbeddingsSearchGetParams) =>
  unwrap<EmbeddingSearchResponse>(searchEmbeddingsSearchGet(params))
