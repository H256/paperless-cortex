import { defineConfig } from 'orval';

const apiUrl = process.env.ORVAL_API_URL || '../backend/openapi.json';

export default defineConfig({
  api: {
    input: {
      target: apiUrl,
    },
    output: {
      target: './src/api/generated/client.ts',
      schemas: './src/api/generated/model',
      client: 'fetch',
      baseUrl: '/api',
      clean: true,
      prettier: true,
    },
  },
});
