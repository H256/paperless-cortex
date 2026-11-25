<template>
  <div class="fixed inset-x-4 top-4 z-50 flex flex-col gap-2 sm:left-auto sm:right-4 sm:w-full sm:max-w-sm">
    <Toast
      v-for="toast in toasts"
      :key="toast.id"
      :title="toast.title"
      :message="toast.count > 1 ? `${toast.message} (×${toast.count})` : toast.message"
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
