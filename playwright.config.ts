import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.BASE_URL ?? 'http://127.0.0.1:4173/TowerSignal/'
const authStateDir = 'test-results/.auth'
const desktopAuthState = process.env.CI ? { storageState: `${authStateDir}/desktop.json` } : {}
const iphoneAuthState = process.env.CI ? { storageState: `${authStateDir}/iphone.json` } : {}

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  // Hosted tests share one temporary account per browser family. Serializing
  // CI avoids concurrent sign-in races against the managed Neon Auth service,
  // while local development keeps Playwright's normal worker behavior.
  workers: process.env.CI ? 1 : undefined,
  use: { baseURL, trace: 'retain-on-failure' },
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
      use: { ...devices['Desktop Chrome'], ...desktopAuthState },
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
      use: { ...devices['iPhone 13'], ...iphoneAuthState },
    },
  ],
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
})
