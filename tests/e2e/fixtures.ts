import { expect, test as base } from '@playwright/test'
import { signInForProject } from './auth.helpers'

export const test = base.extend<{ authenticatedSession: void }>({
  authenticatedSession: [async ({ page }, use, testInfo) => {
    await signInForProject(page, testInfo.project.name, '#/home')
    // WebKit sign-in resolves before the Home component finishes its independent
    // requests. Prove that initial page hydrated before a test leaves it; otherwise
    // legitimate unmount cancellation is recorded as a workspace transport error.
    const intelligence = page.getByRole('region', { name: 'Legionnaires official intelligence' })
    await expect(intelligence.locator('.li-headline').first()).toBeVisible()
    await expect(intelligence.locator('.li-match-button').first()).toBeVisible()
    await expect(intelligence.locator('.li-notice')).toHaveCount(0)
    await use()
  }, { auto: true }],
})

export { expect }
