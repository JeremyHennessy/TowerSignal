import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.BASE_URL ?? 'http://127.0.0.1:4173/TowerSignal/'
const ignoreHTTPSErrors = process.env.ALLOW_SELF_SIGNED === 'true'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: { baseURL, trace: 'retain-on-failure', ignoreHTTPSErrors },
  projects: [
    {
      name: 'setup-desktop',
      testMatch: /auth\.setup\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'desktop-chromium',
      testIgnore: /auth\.setup\.ts/,
      dependencies: ['setup-desktop'],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'setup-iphone',
      testMatch: /auth\.setup\.ts/,
      use: { ...devices['iPhone 13'] },
    },
    {
      name: 'iphone',
      testIgnore: /auth\.setup\.ts/,
      dependencies: ['setup-iphone'],
      use: { ...devices['iPhone 13'] },
    },
  ],
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
})
