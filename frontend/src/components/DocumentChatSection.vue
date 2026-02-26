<template>
  <section
    class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex flex-wrap items-end gap-4">
      <div class="flex-1 min-w-[260px]">
        <label class="text-xs font-medium text-slate-600 dark:text-slate-300">Question</label>
        <div class="mt-1 flex items-center gap-2">
          <input
            ref="questionInputRef"
            v-model="question"
            class="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900 outline-none focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            type="text"
            placeholder="Ask about this document..."
            @keyup.enter="ask"
          />
          <button
            class="inline-flex h-10 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
            :disabled="loading || !question"
            @click="ask"
          >
            <MessageCircle class="h-4 w-4" />
            {{ loading ? 'Thinking...' : 'Ask' }}
          </button>
          <button
            v-if="loading && streaming"
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
          v-model.number="topK"
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
          v-model="source"
          :disabled="onlyVision"
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
          >Min quality: {{ minQuality }}</label
        >
        <input type="range" min="0" max="100" v-model.number="minQuality" class="h-10 w-40" />
      </div>
      <div class="flex flex-col gap-1">
        <label class="text-xs font-medium text-slate-600 whitespace-nowrap dark:text-slate-300"
          >Relationship</label
        >
        <select
          v-model="relationshipMode"
          class="h-10 min-w-[140px] rounded-lg border border-slate-200 bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="none">None</option>
          <option value="chrono">Chrono</option>
        </select>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
          <input type="checkbox" v-model="docScope" class="h-4 w-4" />
          Only this document
        </label>
        <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
          <input type="checkbox" v-model="onlyVision" class="h-4 w-4" />
          Only vision OCR
        </label>
        <label class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
          <input type="checkbox" v-model="streaming" class="h-4 w-4" />
          Streaming
        </label>
        <label
          class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300"
          title="Include recent turns to support follow-up questions."
        >
          <input type="checkbox" v-model="useHistory" class="h-4 w-4" />
          Follow-up context
        </label>
        <label v-if="useHistory" class="inline-flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
          Turns
          <select
            v-model.number="historyTurns"
            class="h-8 min-w-[64px] rounded-lg border border-slate-200 bg-white px-2 text-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option :value="2">2</option>
            <option :value="4">4</option>
            <option :value="6">6</option>
            <option :value="8">8</option>
            <option :value="12">12</option>
          </select>
        </label>
      </div>
    </div>

    <div
      v-if="error"
      class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200"
    >
      {{ error }}
    </div>

    <div class="mt-6 space-y-4">
      <div v-if="messages.length === 0" class="text-sm text-slate-500 dark:text-slate-400">
        No chat responses yet.
      </div>
      <div
        v-else
        v-for="message in messages"
        :key="message.id"
        class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div
          class="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          <span>Question</span>
          <span class="text-[11px] font-normal text-slate-400 dark:text-slate-500">
            {{ formatAge(message.createdAt) }}
          </span>
        </div>
        <div class="mt-2 text-sm text-slate-900 dark:text-slate-100">{{ message.question }}</div>

        <div
          class="mt-4 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
        >
          <span>Answer</span>
          <span
            v-if="loading && messages[0]?.id === message.id"
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

        <div
          class="mt-4 rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300"
        >
          <div class="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Follow-up questions
          </div>
          <div v-if="message.followupsLoading" class="mt-2 inline-flex items-center gap-2 text-xs">
            <span class="chat-dots" aria-hidden="true">
              <span></span><span></span><span></span>
            </span>
            Generating...
          </div>
          <div v-else-if="message.followupsError" class="mt-2 text-rose-600 dark:text-rose-300">
            {{ message.followupsError }}
          </div>
          <div v-else-if="message.followups && message.followups.length" class="mt-2 flex flex-wrap gap-2">
            <button
              v-for="(followup, index) in message.followups"
              :key="`${message.id}-followup-${index}`"
              class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
              @click="askFollowup(followup)"
            >
              {{ followup }}
            </button>
          </div>
          <div v-else class="mt-2 text-xs text-slate-500 dark:text-slate-400">
            No follow-ups available.
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-2">
          <span class="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500"
            >Sources</span
          >
          <span v-if="!message.citations || message.citations.length === 0" class="text-xs text-slate-500 dark:text-slate-400"
            >No citations.</span
          >
          <div v-else class="flex flex-wrap items-center gap-2">
            <div v-for="(citation, idx) in message.citations" :key="`${message.id}-citation-${idx}`" class="relative group">
              <component
                :is="citation.doc_id ? 'a' : 'span'"
                :href="citation.doc_id ? citationLink(citation) : undefined"
                :target="citation.doc_id ? '_blank' : undefined"
                :rel="citation.doc_id ? 'noopener noreferrer' : undefined"
                class="flex h-8 w-8 items-center justify-center rounded-full border bg-white text-slate-500 shadow-sm hover:text-indigo-600 dark:bg-slate-900 dark:text-slate-300"
                :aria-label="`Source ${citation.id}`"
              >
                <BookOpen class="h-4 w-4" />
                <span class="absolute -right-1 -top-1 rounded-full bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
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
    </div>
  </section>
</template>

<script setup lang="ts">
import { BookOpen, MessageCircle } from 'lucide-vue-next'
import { onMounted, ref, watch } from 'vue'
import type { ChatCitation } from '../api/generated/model'
import { buildDocumentCitationLink } from '../services/citationJump'
import { formatRelativeAge, renderChatMarkdown } from '../utils/chatPresentation'
import { useChatSession, type ChatMessage } from '../composables/useChatSession'

const props = defineProps<{
  docId: number
}>()

const {
  question,
  topK,
  source,
  onlyVision,
  minQuality,
  streaming,
  useHistory,
  historyTurns,
  docScope,
  docId,
  relationshipMode,
  loading,
  error,
  messages,
  ask,
  stop,
} = useChatSession({
  storageKey: `paperless_doc_chat_${props.docId}`,
  defaultDocId: props.docId,
  defaultDocScope: true,
  defaultRelationshipMode: 'none',
})

const now = ref(Date.now())
const questionInputRef = ref<HTMLInputElement | null>(null)

const citationLink = (citation: ChatCitation) => {
  return buildDocumentCitationLink({
    docId: citation?.doc_id,
    page: citation?.page,
    bbox: citation?.bbox,
    source: citation?.source,
    snippet: citation?.snippet,
  })
}

const renderMarkdown = (message: ChatMessage) => renderChatMarkdown(message, citationLink)
const formatAge = (timestamp: number) => formatRelativeAge(now.value, timestamp)

const askFollowup = async (text: string) => {
  const value = (text || '').trim()
  if (!value) return
  question.value = value
  await ask()
}

onMounted(() => {
  window.setInterval(() => {
    now.value = Date.now()
  }, 30000)
})

watch(
  () => props.docId,
  (next) => {
    docId.value = next
  },
)
</script>

<style scoped>
.chat-dots {
  display: inline-flex;
  gap: 2px;
}
.chat-dots span {
  width: 4px;
  height: 4px;
  background: currentColor;
  border-radius: 999px;
  animation: pulse 1s ease-in-out infinite;
}
.chat-dots span:nth-child(2) {
  animation-delay: 0.2s;
}
.chat-dots span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-2px);
  }
}
</style>
