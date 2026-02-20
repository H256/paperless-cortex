import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    exclude: ['e2e/**', 'dist/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: './coverage',
      include: [
        'src/utils/queryState.ts',
        'src/utils/writebackPreview.ts',
        'src/utils/number.ts',
        'src/utils/continueProcessingPanel.ts',
        'src/utils/queueView.ts',
        'src/utils/documentDetail.ts',
        'src/composables/useContinueProcessOptions.ts',
        'src/composables/useVisibleDocuments.ts',
        'src/composables/useDocumentProcessingState.ts',
        'src/composables/useDocumentReview.ts',
        'src/composables/useDocumentSuggestionsApply.ts',
        'src/services/chatStream.ts',
      ],
      exclude: ['src/**/*.test.ts'],
      thresholds: {
        lines: 82,
        statements: 82,
        branches: 71,
        functions: 82,
      },
    },
  },
})
