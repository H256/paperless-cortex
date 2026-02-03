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
        <div class="flex items-center gap-4">
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
        </div>
      </div>

      <div
        v-if="chatStore.error"
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
      >
        {{ chatStore.error }}
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
          <span class="text-[11px] font-normal text-slate-400 dark:text-slate-500">{{
            formatAge(message.createdAt)
          }}</span>
        </div>
        <div class="mt-2 text-sm text-slate-900 dark:text-slate-100">{{ message.question }}</div>

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
            v-if="message.citations.length === 0"
            class="text-xs text-slate-500 dark:text-slate-400"
            >No citations.</span
          >
          <div v-else class="flex flex-wrap items-center gap-2">
            <div v-for="citation in message.citations" :key="citation.id" class="relative group">
              <component
                :is="citation.doc_id ? RouterLink : 'span'"
                :to="citation.doc_id ? citationLink(citation) : undefined"
                class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm hover:border-slate-300 hover:text-indigo-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500"
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
import { BookOpen, MessageCircle } from 'lucide-vue-next'
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useChatStore, ChatMessage } from '../stores/chatStore'
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

const encodeBBox = (bbox: unknown) => {
  if (!Array.isArray(bbox) || bbox.length !== 4) return ''
  const nums = bbox.map((value) => Number(value))
  if (nums.some((value) => Number.isNaN(value))) return ''
  return nums.map((value) => value.toFixed(5)).join(',')
}

const citationLink = (citation: any) => {
  if (!citation?.doc_id) return ''
  const params = new URLSearchParams()
  if (citation.page) params.set('page', String(citation.page))
  const bbox = encodeBBox(citation.bbox)
  if (bbox) params.set('bbox', bbox)
  const qs = params.toString()
  return qs ? `/documents/${citation.doc_id}?${qs}` : `/documents/${citation.doc_id}`
}

const renderMarkdown = (message: ChatMessage) => {
  const map = new Map<number, { tooltip: string; href: string }>()
  ;(message.citations || []).forEach((cite) => {
    const tooltip = `Doc ${cite.doc_id ?? 'n/a'} - Page ${cite.page ?? 'n/a'} - ${cite.source || 'unknown'}`
    const href = cite.doc_id ? citationLink(cite) : '#'
    map.set(cite.id, { tooltip, href })
  })
  const withCitations = message.answer.replace(/\\[(\\d+)\\]/g, (match, rawId) => {
    const id = Number(rawId)
    const info = map.get(id)
    if (!info) return match
    return `<sup class="chat-citation" title="${info.tooltip}"><a href="${info.href}" class="chat-citation-link">[${id}]</a></sup>`
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
