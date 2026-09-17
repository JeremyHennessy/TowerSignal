import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /session-bridge-candidate\.spec\.ts/,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4173/TowerSignal/',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'bridge-desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'bridge-iphone', use: { ...devices['iPhone 13'], trace: 'off' } },
  ],
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-session-bridge', open: 'never' }]],
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173/TowerSignal/',
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
