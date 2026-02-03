<template>
  <div class="fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-2">
    <Toast
      v-for="toast in toasts"
      :key="toast.id"
      :title="toast.title"
      :message="toast.message"
      :tone="toast.tone"
      @close="remove(toast.id)"
    />
  </div>
</template>

<script setup lang="ts">
import Toast from './Toast.vue'
import { storeToRefs } from 'pinia'
import { useToastStore } from '../stores/toastStore'

const toastStore = useToastStore()
const { toasts } = storeToRefs(toastStore)

const remove = (id: string) => {
  toastStore.remove(id)
}
</script>
