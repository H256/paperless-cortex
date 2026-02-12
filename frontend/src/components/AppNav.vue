<template>
  <nav class="flex items-center gap-2 text-sm font-medium">
    <RouterLink v-for="item in primaryItems" :key="item.to" :to="item.to" v-slot="{ isActive }">
      <span :class="linkClass(isActive)">
        <component :is="item.icon" class="h-4 w-4" />
        {{ item.label }}
      </span>
    </RouterLink>

    <details
      v-if="secondaryItems.length"
      ref="moreMenuRef"
      class="relative"
      @focusout="onMoreMenuFocusOut"
    >
      <summary
        class="inline-flex cursor-pointer list-none items-center gap-2 rounded-full px-3 py-1 text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
        :class="secondaryActive ? 'bg-indigo-600 text-white hover:text-white' : ''"
      >
        More
      </summary>
      <div
        class="absolute right-0 z-30 mt-2 min-w-44 rounded-lg border border-slate-200 bg-white p-1 shadow-lg dark:border-slate-700 dark:bg-slate-900"
      >
        <RouterLink
          v-for="item in secondaryItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
          @click="closeMoreMenu"
        >
          <component :is="item.icon" class="h-4 w-4" />
          {{ item.label }}
        </RouterLink>
      </div>
    </details>
  </nav>
</template>

<script setup lang="ts">
import { computed, ref, type Component } from 'vue'
import { useRoute } from 'vue-router'

export type NavItem = {
  to: string
  label: string
  icon: Component
}

const route = useRoute()
const moreMenuRef = ref<HTMLDetailsElement | null>(null)

const linkClass = (isActive: boolean) =>
  [
    'inline-flex items-center gap-2 rounded-full px-3 py-1',
    isActive
      ? 'bg-indigo-600 text-white'
      : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
  ]

const props = defineProps<{
  primaryItems: NavItem[]
  secondaryItems: NavItem[]
}>()

const secondaryActive = computed(() =>
  props.secondaryItems.some((item) => route.path === item.to || route.path.startsWith(`${item.to}/`)),
)

const closeMoreMenu = () => {
  if (moreMenuRef.value) moreMenuRef.value.open = false
}

const onMoreMenuFocusOut = (event: FocusEvent) => {
  const container = moreMenuRef.value
  if (!container) return
  const nextTarget = event.relatedTarget as Node | null
  if (nextTarget && container.contains(nextTarget)) return
  closeMoreMenu()
}
</script>
