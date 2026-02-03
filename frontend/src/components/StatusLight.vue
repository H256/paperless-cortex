<template>
  <div class="inline-flex items-center gap-2" :title="title">
    <span :class="dotClass"></span>
    <span>{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
  label: string
  title?: string
}>()

const dotClass = computed(
  () => `h-2 w-2 rounded-full ${props.status === 'UP' ? 'bg-emerald-500' : 'bg-rose-500'}`,
)
</script>
