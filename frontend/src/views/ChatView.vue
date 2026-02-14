<template>
  <section>
    <div>
      <h2 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Chat</h2>
      <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Ask questions and get answers with document citations.
      </p>
    </div>

    <section
      class="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex-1 min-w-[260px]">
          <label class="text-xs font-medium text-slate-600 dark:text-slate-300">Question</label>
          <div class="mt-1 flex items-center gap-2">
            <input
              v-model="chatStore.question"
              class="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900 outline-none focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              type="text"
              placeholder="Ask a question about your documents..."
              @keyup.enter="ask"
            />
            <button
              class="inline-flex h-10 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
              :disabled="chatStore.loading || askLoading || !chatStore.question"
              @click="ask"
            >
              <MessageCircle class="h-4 w-4" />
              {{ chatStore.loading ? 'Thinking...' : 'Ask' }}
            </button>
            <button
              v-if="chatStore.loading && chatStore.streaming"
              class="inline-flex h-10 items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 text-sm font-semibold text-rose-700 shadow-sm hover:border-rose-300 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
              @click="stop"
            >
              Stop
            </button>
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap dark:text-slate-300"
            >Top K</label
          >
          <select
            v-model.number="chatStore.topK"
            class="h-10 min-w-[84px] rounded-lg border border-slate-200 bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option :value="3">3</option>
            <option :value="6">6</option>
            <option :value="10">10</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap dark:text-slate-300"
            >Source</label
          >
          <select
            v-model="chatStore.source"
            :disabled="chatStore.onlyVision"
            class="h-10 min-w-[160px] rounded-lg border border-slate-200 bg-white px-2 text-sm disabled:bg-slate-100 disabled:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:disabled:bg-slate-800 dark:disabled:text-slate-500"
          >
            <option value="">All</option>
            <option value="vision_ocr">Vision OCR</option>
            <option value="paperless_ocr">Paperless OCR</option>
            <option value="pdf_text">PDF text</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-slate-600 whitespace-nowrap dark:text-slate-300"
            >Min quality: {{ chatStore.minQuality }}</label
          >
          <input
            type="range"
            min="0"
            max="100"
            v-model.number="chatStore.minQuality"
            class="h-10 w-40"
          />
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <label
            class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            <input type="checkbox" v-model="chatStore.onlyVision" class="h-4 w-4" />
            Only vision OCR
          </label>
          <label
            class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            <input type="checkbox" v-model="chatStore.streaming" class="h-4 w-4" />
            Streaming
          </label>
          <label
            class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
            title="Include recent turns to support follow-up questions."
          >
            <input type="checkbox" v-model="chatStore.useHistory" class="h-4 w-4" />
            Follow-up context
          </label>
          <label
            v-if="chatStore.useHistory"
            class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            Turns
            <select
              v-model.number="chatStore.historyTurns"
              class="h-8 min-w-[64px] rounded-lg border border-slate-200 bg-white px-2 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option :value="2">2</option>
              <option :value="4">4</option>
              <option :value="6">6</option>
              <option :value="8">8</option>
              <option :value="12">12</option>
            </select>
          </label>
          <button
            class="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="chatStore.loading"
            @click="chatStore.newConversation()"
          >
            <MessageSquarePlus class="h-3.5 w-3.5" />
            New thread
          </button>
          <button
            class="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="chatStore.loading || chatStore.messages.length === 0"
            @click="chatStore.clearConversation()"
          >
            <Trash2 class="h-3.5 w-3.5" />
            Clear
          </button>
        </div>
      </div>

      <div
        v-if="chatStore.error"
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        {{ chatStore.error }}
      </div>
      <div class="mt-3 text-xs text-slate-500 dark:text-slate-400">
        Conversation:
        <code class="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-800">
          {{ chatStore.conversationId || 'new (will be created on next question)' }}
        </code>
      </div>
    </section>

    <section class="mt-6 space-y-4">
      <div
        v-if="chatStore.messages.length === 0"
        class="text-sm text-slate-500 dark:text-slate-400"
      >
        No chat responses yet.
      </div>
      <div
        v-else
        v-for="message in chatStore.messages"
        :key="message.id"
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          <span>Question</span>
          <span class="text-[11px] font-normal text-slate-400 dark:text-slate-500">
            {{ formatAge(message.createdAt) }}
            <template v-if="message.conversationId"> · {{ shortConversationId(message.conversationId) }}</template>
          </span>
        </div>
        <div class="mt-2 text-sm text-slate-900 dark:text-slate-100">{{ message.question }}</div>
        <div class="mt-2">
          <button
            class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
            :disabled="chatStore.loading"
            @click="chatStore.startFollowUp(message.question)"
          >
            <CornerDownRight class="h-3.5 w-3.5" />
            Follow-up
          </button>
        </div>

        <div
          class="mt-4 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          <span>Answer</span>
          <span
            v-if="chatStore.loading && chatStore.messages[0]?.id === message.id"
            class="inline-flex items-center gap-2 text-[11px] font-normal text-slate-500 dark:text-slate-400"
          >
            Thinking
            <span class="chat-dots" aria-hidden="true">
              <span></span><span></span><span></span>
            </span>
          </span>
        </div>
        <div
          class="mt-2 text-sm text-slate-900 prose prose-slate max-w-none dark:prose-invert dark:text-slate-100"
          v-html="renderMarkdown(message)"
        ></div>

        <div class="mt-4 flex flex-wrap items-center gap-2">
          <span
            class="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
            >Sources</span
          >
          <span
            v-if="!message.citations || message.citations.length === 0"
            class="text-xs text-slate-500 dark:text-slate-400"
            >No citations.</span
          >
          <div v-else class="flex flex-wrap items-center gap-2">
            <div
              v-for="(citation, idx) in message.citations"
              :key="citationKey(citation, idx)"
              class="relative group"
            >
              <component
                :is="citation.doc_id ? 'a' : 'span'"
                :href="citation.doc_id ? citationLink(citation) : undefined"
                :target="citation.doc_id ? '_blank' : undefined"
                :rel="citation.doc_id ? 'noopener noreferrer' : undefined"
                class="flex h-8 w-8 items-center justify-center rounded-full border bg-white text-slate-500 shadow-sm hover:text-indigo-600 dark:bg-slate-900 dark:text-slate-300"
                :class="citationClass(citation)"
                :aria-label="`Source ${citation.id}`"
              >
                <BookOpen class="h-4 w-4" />
                <span
                  class="absolute -right-1 -top-1 rounded-full bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold text-white"
                >
                  {{ citation.id }}
                </span>
              </component>
              <div
                class="pointer-events-none absolute bottom-full right-0 z-10 mb-2 w-72 translate-y-2 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 opacity-0 shadow-lg transition group-hover:translate-y-0 group-hover:opacity-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              >
                <div class="flex items-center justify-between">
                  <span class="font-semibold">Source {{ citation.id }}</span>
                </div>
                <div class="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                  Doc {{ citation.doc_id ?? 'n/a' }} - Page {{ citation.page ?? 'n/a' }} -
                  {{ citation.source || 'unknown' }}
                </div>
                <div class="mt-1 text-[11px] text-slate-600 dark:text-slate-400">
                  Score {{ formatScore(citation.score) }} - Quality
                  {{ citation.quality_score ?? 'n/a' }}
                </div>
                <div
                  v-if="evidenceStatus(citation)"
                  class="mt-1 text-[11px]"
                  :class="
                    evidenceStatus(citation) === 'ok'
                      ? 'text-emerald-600 dark:text-emerald-300'
                      : evidenceStatus(citation) === 'no_match'
                        ? 'text-amber-600 dark:text-amber-300'
                        : 'text-rose-600 dark:text-rose-300'
                  "
                >
                  Evidence: {{ evidenceStatus(citation) }}
                  <template v-if="evidenceConfidence(citation) !== null">
                    ({{ evidenceConfidence(citation) }})
                  </template>
                  <template v-if="evidenceError(citation)"> - {{ evidenceError(citation) }}</template>
                </div>
                <div
                  v-if="citation.snippet"
                  class="mt-2 text-xs text-slate-700 dark:text-slate-200"
                >
                  {{ citation.snippet }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { BookOpen, MessageCircle, CornerDownRight, MessageSquarePlus, Trash2 } from 'lucide-vue-next'
import { onMounted, onUnmounted, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useChatStore } from '../stores/chatStore'
import type { ChatMessage } from '../stores/chatStore'
import type { ChatCitation } from '../services/chat'
import { buildDocumentCitationLink } from '../services/citationJump'
import { useLoading } from '../composables/useLoading'

const chatStore = useChatStore()
const { loading: askLoading, run: runAsk } = useLoading()
const now = ref(Date.now())

const ask = async () => {
  await runAsk(() => chatStore.ask())
}

const stop = () => {
  chatStore.stop()
}

const citationLink = (citation: ChatCitation) => {
  return buildDocumentCitationLink({
    docId: citation?.doc_id,
    page: citation?.page,
    bbox: citation?.bbox,
    source: citation?.source,
    snippet: citation?.snippet,
  })
}

const citationKey = (citation: ChatCitation, idx: number) =>
  `${citation.id ?? 'x'}-${citation.doc_id ?? 'doc'}-${citation.page ?? 'p'}-${idx}`

const evidenceStatus = (citation: ChatCitation): string => {
  return typeof citation.evidence_status === 'string' ? citation.evidence_status : ''
}

const evidenceConfidence = (citation: ChatCitation): string | null => {
  const value = citation.evidence_confidence
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  return value.toFixed(2)
}

const evidenceError = (citation: ChatCitation): string => {
  return typeof citation.evidence_error === 'string' ? citation.evidence_error : ''
}

const citationClass = (citation: ChatCitation): string => {
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

const renderMarkdown = (message: ChatMessage) => {
  const escapeAttr = (value: string) =>
    value
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')

  const map = new Map<number, { tooltip: string; href: string }>()
  ;(message.citations || []).forEach((cite) => {
    const tooltip = `Doc ${cite.doc_id ?? 'n/a'} - Page ${cite.page ?? 'n/a'} - ${cite.source || 'unknown'}`
    const href = cite.doc_id ? citationLink(cite) : ''
    map.set(cite.id, { tooltip, href })
  })
  const withCitations = message.answer.replace(/\\[(\\d+)\\]/g, (match, rawId) => {
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

const formatAge = (timestamp: number) => {
  void now.value
  const diff = Math.max(0, Date.now() - timestamp)
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

let timer: number | null = null
onMounted(() => {
  timer = window.setInterval(() => {
    now.value = Date.now()
  }, 30000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})

const formatScore = (score?: number | null) => {
  if (score === undefined || score === null) return 'n/a'
  return score.toFixed ? score.toFixed(3) : String(score)
}

const shortConversationId = (value: string) => {
  const id = (value || '').trim()
  if (!id) return ''
  if (id.length <= 14) return id
  return `${id.slice(0, 8)}...${id.slice(-4)}`
}
</script>

<style scoped>
.chat-citation {
  margin-left: 2px;
}

.chat-citation-link {
  color: #4f46e5;
  font-weight: 600;
  text-decoration: none;
}

.chat-citation-link:hover {
  text-decoration: underline;
}

.chat-dots {
  display: inline-flex;
  gap: 4px;
}

.chat-dots span {
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: #94a3b8;
  display: inline-block;
  animation: chat-bounce 1s infinite ease-in-out;
}

.chat-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.chat-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes chat-bounce {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.6;
  }
  50% {
    transform: translateY(-3px);
    opacity: 1;
  }
}
</style>
