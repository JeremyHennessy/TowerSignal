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

function slug(project: string) {
  return project.toLowerCase().replace(/[^a-z0-9]+/g, '-')
}

async function seedWorkflow(page: import('@playwright/test').Page, projectName: string) {
  for (const [index, systemId] of REVIEW_ACCOUNTS.entries()) {
    if (index === 0) await signInForProject(page, projectName, `#/account/${systemId}`)
    else await page.goto(`./#/account/${systemId}`, { waitUntil: 'networkidle' })

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
      await delay(35)
    }
    window.scrollTo(0, 0)
  })
  await page.waitForTimeout(300)
}

async function shot(page: import('@playwright/test').Page, name: string, project: string) {
  await warmFullPage(page)
  await page.screenshot({ path: `review-artifacts/${name}-${slug(project)}.png`, fullPage: true })
}

test('live Workflow and account round two visual acceptance', async ({ page }, testInfo) => {
  testInfo.setTimeout(420_000)
  const project = testInfo.project.name
  await seedWorkflow(page, project)

  await page.goto('./#/workflow', { waitUntil: 'networkidle' })
  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible({ timeout: 30_000 })
  await expect(workflow.getByRole('heading', { name: 'Workflow workspace', exact: true })).toBeVisible()
  await expect(workflow.locator('.workflow-command-table')).toBeVisible()
  await expect(workflow.locator('.workflow-command-map')).toBeVisible()

  const statusFilter = workflow.getByLabel('Workflow status filter')
  await statusFilter.selectOption('investigate')
  const firstRow = workflow.locator('.workflow-command-table tbody tr').first()
  await expect(firstRow).toBeVisible()
  await firstRow.click()
  await expect(workflow.locator('.workflow-account-inspector')).toBeVisible()
  await shot(page, 'workflow-full', project)

  await workflow.getByRole('button', { name: /Open full account/ }).click()
  await expect(page).toHaveURL(/#\/account\//)
  await expect(page.getByRole('button', { name: /Back to Workflow/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What matters before the next action' })).toBeVisible()
  await shot(page, 'account-summary', project)

  for (const mode of ['Sales', 'Field', 'Evidence', 'History'] as const) {
    await page.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
    await page.waitForTimeout(250)
    await shot(page, `account-${mode.toLowerCase()}`, project)
  }

  await page.getByRole('button', { name: /Back to Workflow/ }).click()
  await expect(page).toHaveURL(/#\/workflow$/)
  await expect(statusFilter).toHaveValue('investigate')
  await shot(page, 'workflow-returned', project)
})
