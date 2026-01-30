<template>
  <span
    v-if="disabled"
    :title="title"
    :aria-label="ariaLabel"
    class="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-slate-100 p-2 text-slate-400"
  >
    <slot />
  </span>
  <component
    v-else
    :is="href ? 'a' : 'button'"
    :href="href"
    :target="href ? '_blank' : undefined"
    :rel="href ? 'noopener' : undefined"
    :title="title"
    :aria-label="ariaLabel"
    class="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white p-2 text-slate-700 shadow-sm hover:border-slate-300"
  >
    <slot />
  </component>
</template>

<script setup lang="ts">
defineProps<{
  href?: string;
  title?: string;
  ariaLabel?: string;
  disabled?: boolean;
}>();
</script>
