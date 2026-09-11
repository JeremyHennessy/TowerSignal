import { defineConfig, devices } from '@playwright/test'

// Data transport acceptance only. This does not exercise hosted login or UI.
export default defineConfig({
  testDir: './tests/data-only',
  timeout: 120_000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:4173/', trace: 'retain-on-failure' },
  projects: [
    { name: 'data-chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'data-webkit', use: { ...devices['iPhone 13'] } },
  ],
  webServer: {
    command: 'python -m http.server 4173 --bind 127.0.0.1 --directory dist',
    url: 'http://127.0.0.1:4173/data/source-health.json',
    timeout: 60_000,
    reuseExistingServer: false,
  },
  reporter: [['list'], ['html', { outputFolder: 'data-browser-report', open: 'never' }]],
})
