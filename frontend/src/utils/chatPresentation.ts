import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatCitation } from '../api/generated/model'
import type { ChatMessage } from '../composables/useChatSession'

const escapeAttr = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

export const citationKey = (citation: ChatCitation, idx: number) =>
  `${citation.id ?? 'x'}-${citation.doc_id ?? 'doc'}-${citation.page ?? 'p'}-${idx}`

export const evidenceStatus = (citation: ChatCitation): string => {
  return typeof citation.evidence_status === 'string' ? citation.evidence_status : ''
}

export const evidenceConfidence = (citation: ChatCitation): string | null => {
  const value = citation.evidence_confidence
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  return value.toFixed(2)
}

export const evidenceError = (citation: ChatCitation): string => {
  return typeof citation.evidence_error === 'string' ? citation.evidence_error : ''
}

export const citationClass = (citation: ChatCitation): string => {
  const status = evidenceStatus(citation)
  if (status === 'ok') {
    return 'border-emerald-200 hover:border-emerald-300 dark:border-emerald-900/50 dark:hover:border-emerald-700'
  }
  if (status === 'no_match') {
    return 'border-amber-200 hover:border-amber-300 dark:border-amber-900/50 dark:hover:border-amber-700'
  }
  if (status === 'error') {
    return 'border-rose-200 hover:border-rose-300 dark:border-rose-900/50 dark:hover:border-rose-700'
  }
  return 'border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-500'
}

export const renderChatMarkdown = (
  message: ChatMessage,
  citationHref: (citation: ChatCitation) => string,
): string => {
  const map = new Map<number, { tooltip: string; href: string }>()
  ;(message.citations || []).forEach((cite) => {
    const tooltip = `Doc ${cite.doc_id ?? 'n/a'} - Page ${cite.page ?? 'n/a'} - ${cite.source || 'unknown'}`
    const href = cite.doc_id ? citationHref(cite) : ''
    map.set(cite.id, { tooltip, href })
  })
  const withCitations = message.answer.replace(/\[(\d+)\]/g, (match, rawId) => {
    const id = Number(rawId)
    const info = map.get(id)
    if (!info) return match
    if (!info.href) {
      return `<sup class="chat-citation" title="${escapeAttr(info.tooltip)}">[${id}]</sup>`
    }
    return `<sup class="chat-citation" title="${escapeAttr(info.tooltip)}"><a href="${escapeAttr(info.href)}" class="chat-citation-link" target="_blank" rel="noopener noreferrer">[${id}]</a></sup>`
  })
  const html = marked.parse(withCitations) as string
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'a',
      'p',
      'strong',
      'em',
      'ul',
      'ol',
      'li',
      'code',
      'pre',
      'blockquote',
      'br',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'sup',
    ],
    ALLOWED_ATTR: ['href', 'title', 'class', 'target', 'rel'],
    FORBID_TAGS: ['style', 'script'],
    FORBID_ATTR: ['style', 'onerror', 'onload', 'onclick'],
    ALLOWED_URI_REGEXP: /^(https?:|mailto:|tel:|\/)/i,
  })
}

export const formatRelativeAge = (nowMs: number, timestamp: number): string => {
  const diff = Math.max(0, nowMs - timestamp)
  const seconds = Math.floor(diff / 1000)
  if (seconds < 10) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export const formatScore = (score?: number | null): string => {
  if (score === undefined || score === null) return 'n/a'
  return score.toFixed ? score.toFixed(3) : String(score)
}

export const shortConversationId = (value: string): string => {
  const id = (value || '').trim()
  if (!id) return ''
  if (id.length <= 14) return id
  return `${id.slice(0, 8)}...${id.slice(-4)}`
}
