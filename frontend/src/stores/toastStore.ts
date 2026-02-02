import { defineStore } from 'pinia';

export type ToastTone = 'info' | 'success' | 'warning' | 'danger';

export type ToastItem = {
  id: string;
  title?: string;
  message: string;
  tone: ToastTone;
};

export const useToastStore = defineStore('toasts', {
  state: () => ({
    toasts: [] as ToastItem[],
  }),
  actions: {
    push(message: string, tone: ToastTone = 'info', title?: string, durationMs = 1400) {
      const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      this.toasts.push({ id, message, tone, title });
      window.setTimeout(() => {
        this.remove(id);
      }, durationMs);
    },
    remove(id: string) {
      this.toasts = this.toasts.filter((toast) => toast.id !== id);
    },
  },
});
