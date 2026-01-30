import { defineStore } from 'pinia';

export interface AppError {
  id: string;
  message: string;
  detail?: string;
  createdAt: number;
}

const makeId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;

export const useErrorStore = defineStore('errors', {
  state: () => ({
    errors: [] as AppError[],
  }),
  actions: {
    add(message: string, detail?: string, ttl = 6000) {
      const error: AppError = { id: makeId(), message, detail, createdAt: Date.now() };
      this.errors.unshift(error);
      if (ttl > 0) {
        window.setTimeout(() => this.remove(error.id), ttl);
      }
    },
    remove(id: string) {
      this.errors = this.errors.filter((err) => err.id !== id);
    },
    clear() {
      this.errors = [];
    },
  },
});
