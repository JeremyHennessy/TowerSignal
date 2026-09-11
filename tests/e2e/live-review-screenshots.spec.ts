import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

const REVIEW_ACCOUNTS = [
  '2000015564',
  '2000001368',
  '2000002469',
  '2000000869',
  '2000000584',
  '2000001968',
]

async function seedWorkflow(page: import('@playwright/test').Page, projectName: string) {
  for (const [index, systemId] of REVIEW_ACCOUNTS.entries()) {
    if (index === 0) {
      await signInForProject(page, projectName, `#/account/${systemId}`)
    } else {
      await page.goto(`./#/account/${systemId}`, { waitUntil: 'networkidle' })
    }

    const section = page.locator('section.workflow-account-section')
    await expect(section).toBeVisible({ timeout: 30_000 })
    const status = index === 0 ? 'investigate' : index === 1 ? 'monitor' : index === 2 ? 'contacted' : index === 3 ? 'follow-up' : 'investigate'
    await section.getByLabel('Status').selectOption(status)
    if (index === 0 || index === 2) {
      const date = new Date()
      date.setDate(date.getDate() + (index === 0 ? -1 : 3))
      await section.getByLabel('Next action').fill(date.toISOString().slice(0, 10))
    } else {
      await section.getByLabel('Next action').fill('')
    }
    await section.getByLabel('Private note').fill(index % 2 === 0 ? 'Review compliance and service evidence before outreach.' : '')
    await section.getByRole('button', { name: 'Save workflow state', exact: true }).click()
    await expect(section.getByText('Saved', { exact: true })).toBeVisible({ timeout: 15_000 })
  }
}

async function warmFullPage(page: import('@playwright/test').Page) {
  await page.evaluate(async () => {
    const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
    const step = Math.max(500, Math.floor(window.innerHeight * 0.8))
    for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
      window.scrollTo(0, y)
      await delay(50)
    }
    window.scrollTo(0, document.documentElement.scrollHeight)
    await delay(300)
    window.scrollTo(0, 0)
  })
  await page.waitForTimeout(500)
}

test('capture full live Workflow and representative account drillthrough', async ({ page }, testInfo) => {
  testInfo.setTimeout(360_000)
  await seedWorkflow(page, testInfo.project.name)

  await page.goto('./#/workflow', { waitUntil: 'networkidle' })
  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible({ timeout: 30_000 })
  await expect(workflow.getByRole('heading', { name: 'Workflow workspace', exact: true })).toBeVisible()
  const firstRow = workflow.locator('.workflow-command-table tbody tr').first()
  if (await firstRow.count()) await firstRow.click()
  await warmFullPage(page)
  await page.screenshot({ path: 'review-artifacts/live-workflow-full-desktop.png', fullPage: true })

  await page.goto('./#/account/2000015564', { waitUntil: 'networkidle' })
  await expect(page.locator('main')).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('body')).not.toContainText('Intelligence workspace unavailable')
  await warmFullPage(page)
  await page.screenshot({ path: 'review-artifacts/live-account-2000015564-full-desktop.png', fullPage: true })
})
