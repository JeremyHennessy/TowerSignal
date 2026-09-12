import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import {
  clickElement,
  expectAccountDetailHydrated,
  expectContained,
  expectDomAttribute,
  expectDomCount,
  expectDomText,
  expectElementContained,
  isIphoneProject,
  setWorkflowAccountFields,
} from './iphone.helpers'

test.setTimeout(120_000)

test('workflow command center scales account monitoring across desktop and iPhone', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(240_000)
  const consoleErrors: string[] = []
  const sameOriginFailures: string[] = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('requestfailed', request => {
    try {
      if (new URL(request.url()).origin === new URL(testInfo.project.use.baseURL as string).origin) {
        sameOriginFailures.push(`${request.url()} :: ${request.failure()?.errorText}`)
      }
    } catch { /* ignore non-URL diagnostics */ }
  })

  await signInForProject(page, testInfo.project.name, '#/account/2000015564')
  const workflowAccount = page.locator('section.workflow-account-section')
  if (isIphone) {
    await expectDomCount(page, 'section.workflow-account-section', 1)
    await expectAccountDetailHydrated(page)
  } else {
    await expect(workflowAccount).toBeVisible()
    await workflowAccount.getByLabel('Status').selectOption('investigate')
  }

  const today = new Date().toISOString().slice(0, 10)
  const note = 'Review roof and domestic-water evidence before outreach.'
  if (isIphone) {
    await setWorkflowAccountFields(page, 'section.workflow-account-section', 'investigate', today, note)
    await page.waitForTimeout(100)
    await clickElement(page, 'section.workflow-account-section .workflow-save')
    await expectDomText(page, ['Saved'], 'section.workflow-account-section')
  } else {
    await workflowAccount.getByLabel('Next action').fill(today)
    await workflowAccount.getByLabel('Private note').fill(note)
    await workflowAccount.getByRole('button', { name: 'Save workflow state', exact: true }).click()
    await expect(workflowAccount.getByText('Saved', { exact: true })).toBeVisible()
  }

  await page.evaluate(() => { window.location.hash = '#/workflow' })
  const workflow = page.locator('section.workflow-workspace-page')

  if (isIphone) {
    await expectDomAttribute(page, 'section.workflow-workspace-page h1', 'aria-label', 'Workflow workspace')
    await expectDomText(page, [
      'Workflow scope',
      'NYC market',
      'Due / overdue',
      'Changed · 7d',
      'High priority',
      'Needs a date',
      'Contact-ready',
      'Pipeline',
      'Accounts',
      'Changes',
      'Actions',
      '16 E 39TH ST',
      'Investigate',
      'Portfolio evidence coverage',
    ], 'section.workflow-workspace-page')

    const viewportWidth = page.viewportSize()?.width ?? 0
    const layout = await page.evaluate(() => {
      const grid = document.querySelector('.workflow-command-grid')?.getBoundingClientRect()
      const primary = document.querySelector('.workflow-command-primary')?.getBoundingClientRect()
      const map = document.querySelector('.workflow-command-map')?.getBoundingClientRect()
      const inspector = document.querySelector('.workflow-account-inspector')?.getBoundingClientRect()
      const table = document.querySelector('.workflow-command-table-card')?.getBoundingClientRect()
      return { grid, primary, map, inspector, table, bodyWidth: document.body.scrollWidth }
    })
    expect(layout.bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
    for (const box of [layout.grid, layout.primary, layout.map, layout.inspector, layout.table]) {
      expect(box?.width ?? 0).toBeGreaterThan(0)
      expect(box!.width).toBeLessThanOrEqual(viewportWidth + 0.5)
    }
    expect(layout.inspector!.top).toBeGreaterThanOrEqual(layout.map!.bottom - 1)

    const row = workflow.locator('.workflow-command-table tbody tr', { hasText: '16 E 39TH ST' }).first()
    await row.scrollIntoViewIfNeeded()
    await row.click()
    await expect(workflow.locator('.workflow-account-inspector')).toContainText('16 E 39TH ST')
    await expect(workflow.locator('.workflow-account-inspector')).toContainText(note)
  } else {
    await expect(workflow).toBeVisible()
    await expect(workflow.getByRole('heading', { name: 'Workflow workspace', exact: true })).toBeVisible()
    await expect(workflow.locator('.workflow-command-strip')).toContainText('Due / overdue')
    await expect(workflow.locator('.workflow-command-strip')).toContainText('Changed · 7d')
    await expect(workflow.locator('.workflow-command-strip')).toContainText('High priority')
    await expect(workflow.locator('.workflow-pipeline-strip')).toContainText('Investigate')
    await expect(workflow.locator('.workflow-command-tabs')).toContainText('Accounts')
    await expect(workflow.locator('.workflow-command-tabs')).toContainText('Changes')
    await expect(workflow.locator('.workflow-command-tabs')).toContainText('Actions')
    await expect(workflow.locator('.workflow-command-table-card')).toContainText('16 E 39TH ST')
    await expect(workflow).not.toContainText('Invalid Date')

    const accountRow = workflow.locator('.workflow-command-table tbody tr', { hasText: '16 E 39TH ST' }).first()
    await accountRow.click()
    const inspector = workflow.locator('.workflow-account-inspector')
    await expect(inspector).toContainText('16 E 39TH ST')
    await expect(inspector).toContainText('Investigate')
    await expect(inspector).toContainText(note)
    await expect(inspector.getByRole('button', { name: 'Open full account →' })).toBeVisible()

    const coverage = workflow.locator('details.workflow-coverage-details')
    await coverage.locator('summary').click()
    await expect(coverage).toContainText('Compliance & timing')
    await expect(coverage).toContainText('Ownership & access')
    await expect(coverage).toContainText('Domestic water')
    await expect(coverage).toContainText('Monitoring & change')
    await expect(coverage).toContainText('Field service operations')
    await expect(coverage).toContainText('Relationships & contracts')
  }

  await expectContained(page)
  if (isIphone) {
    await expectElementContained(page, 'section.workflow-workspace-page')
  } else {
    const viewportWidth = page.viewportSize()?.width ?? 0
    const workflowBox = await workflow.boundingBox()
    expect(workflowBox).not.toBeNull()
    expect(workflowBox!.width).toBeLessThanOrEqual(viewportWidth + 0.5)

    const commandShot = await workflow.locator('.workflow-command-center').screenshot()
    await testInfo.attach(`workflow-command-center-${testInfo.project.name}.png`, { body: commandShot, contentType: 'image/png' })
  }

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})