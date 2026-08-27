import { expect, test as base } from '@playwright/test'
import { signInForProject } from './auth.helpers'

export const test = base.extend<{ authenticatedSession: void }>({
  authenticatedSession: [async ({ page }, use, testInfo) => {
    await signInForProject(page, testInfo.project.name, '#/home')
    await use()
  }, { auto: true }],
})

export { expect }
