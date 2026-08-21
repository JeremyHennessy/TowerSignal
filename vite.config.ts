import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/TowerSignal/',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './tests/frontend/setup.ts',
    globals: true,
  },
})
