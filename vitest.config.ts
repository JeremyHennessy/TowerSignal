import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: './tests/frontend/setup.ts',
    globals: true,
    include: ['tests/frontend/**/*.test.{ts,tsx}'],
  },
})
