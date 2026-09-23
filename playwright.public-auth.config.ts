import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.BASE_URL ?? 'http://127.0.0.1:4173/TowerSignal/'

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /auth-public\.spec\.ts/,
  timeout: 45_000,
  expect: { timeout: 15_000 },
  workers: 1,
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'public-desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'public-iphone', use: { ...devices['iPhone 13'] } },
  ],
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
})
