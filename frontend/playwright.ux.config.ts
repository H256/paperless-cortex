import { defineConfig } from '@playwright/test'

// UX evidence run (docs/ux-evidence): stubbed API, accessibility and layout only.
export default defineConfig({
  testDir: './e2e-ux',
  timeout: 60_000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:4173' },
  webServer: {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173',
    port: 4173,
    reuseExistingServer: true,
    timeout: 180_000,
  },
})
