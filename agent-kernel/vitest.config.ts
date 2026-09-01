import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['packages/*/tests/**/*.spec.ts'],
    exclude: ['deepseek-harness/**'],
    testTimeout: 30_000,
    hookTimeout: 30_000,
  },
})
