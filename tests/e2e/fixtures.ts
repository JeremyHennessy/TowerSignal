import { expect, test as base } from '@playwright/test'
import { signInForProject } from './auth.helpers'

export const test = base.extend({})

// Navigate after Playwright has initialized the test context and trace hooks.
// The previous auto fixture performed navigation during fixture setup, before
// the desktop candidate trace was attached. Keep the same real sign-in and
// Home-route assertions, but run them in the normal beforeEach lifecycle.
test.beforeEach(async ({ page }, testInfo) => {
  const lifecycle: string[] = []
  page.on('crash', () => lifecycle.push('page crashed'))
  page.on('close', () => lifecycle.push('page closed'))
  page.context().on('close', () => lifecycle.push('context closed'))
  try {
    await signInForProject(page, testInfo.project.name, '#/home')
  } catch (error) {
    await testInfo.attach('authentication-setup-lifecycle', {
      body: JSON.stringify({ lifecycle, url: page.url(), message: String(error) }),
      contentType: 'application/json',
    })
    throw error
  }
})

export { expect }
