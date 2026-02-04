<template>
  <nav class="flex items-center gap-2 text-sm font-medium">
    <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" v-slot="{ isActive }">
      <span
        :class="[
          'inline-flex items-center gap-2 rounded-full px-3 py-1',
          isActive
            ? 'bg-indigo-600 text-white'
            : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
        ]"
      >
        <component :is="item.icon" class="h-4 w-4" />
        {{ item.label }}
      </span>
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { ChartPie, FileText, List, MessageCircle, Search, Wrench } from 'lucide-vue-next'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: ChartPie },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/chat', label: 'Chat', icon: MessageCircle },
  { to: '/queue', label: 'Queue', icon: List },
  { to: '/operations', label: 'Operations', icon: Wrench },
]
</script>
