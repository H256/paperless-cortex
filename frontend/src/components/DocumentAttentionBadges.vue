<template>
  <div v-if="badges.length" class="flex flex-wrap items-center gap-1" data-testid="attention-badges">
    <span
      v-for="badge in badges"
      :key="badge.key"
      class="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
      :title="badge.title"
      :data-testid="`attention-${badge.key}`"
    >
      {{ badge.label }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DocumentRow } from '../services/documents'
import { attentionBadges } from '../utils/documentAttention'

const props = defineProps<{ doc: DocumentRow }>()
const badges = computed(() => attentionBadges(props.doc))
</script>
