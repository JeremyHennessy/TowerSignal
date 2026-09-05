import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import {
  clickElement,
  expectAccountDetailHydrated,
  expectContained,
  expectDomAttribute,
  expectDomText,
  expectElementContained,
  isIphoneProject,
  setWorkflowAccountFields,
} from './iphone.helpers'

test.setTimeout(120_000)

test('workflow command center groups current and future intelligence on desktop and iPhone', async ({ page }, testInfo) => {
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
    await expect(workflowAccount).toHaveCount(1)
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
  const categories = ['Compliance & timing', 'Ownership, access & property', 'Field & physical', 'Domestic water', 'Monitoring & change', 'Commercial readiness']
  if (isIphone) {
    await expectDomAttribute(page, 'section.workflow-workspace-page h1', 'aria-label', 'Workflow workspace')
    await expectDomText(page, [
      'What matters now',
      'Your private workflow covers 1 current NYC account',
      '1 due or overdue action',
      'NYC market',
      '16 E 39TH ST',
      'Action due today',
      'Investigate',
      ...categories,
      'Cooling-tower roof geometry',
      'DOHMH oversight',
      'Recent ACRIS activity',
      'Future-ready',
      'Review roof and domestic-water evidence before outreach.',
      'Field service operations',
      'Documents & system topology',
      'Relationships & contracts',
    ], 'section.workflow-workspace-page')
  } else {
    await expect(workflow).toBeVisible()
    await expect(workflow.getByRole('heading', { name: 'Workflow workspace', exact: true })).toBeVisible()

    const summary = workflow.locator('.workflow-command-summary')
    await expect(summary.getByRole('heading', { name: 'What matters now', exact: true })).toBeVisible()
    await expect(summary).toContainText('Your private workflow covers 1 current NYC account')
    await expect(summary).toContainText('1 due or overdue action')
    await expect(summary).toContainText('NYC market')

    const attention = workflow.locator('.workflow-attention-list')
    await expect(attention).toContainText('16 E 39TH ST')
    await expect(attention).toContainText('Action due today')
    await expect(attention).toContainText('Investigate')

    for (const category of categories) {
      await expect(workflow.locator('.workflow-intelligence-card', { hasText: category })).toBeVisible()
    }
    await expect(workflow).toContainText('Cooling-tower roof geometry')
    await expect(workflow).toContainText('DOHMH oversight')
    await expect(workflow).toContainText('Recent ACRIS activity')
    await expect(workflow).toContainText('Future-ready')

    await expect(workflow.locator('.workflow-next-actions')).toContainText('Review roof and domestic-water evidence before outreach.')
    await expect(workflow.locator('.workflow-kanban')).toContainText('16 E 39TH ST')
    await expect(workflow.locator('.workflow-future-grid')).toContainText('Field service operations')
    await expect(workflow.locator('.workflow-future-grid')).toContainText('Documents & system topology')
    await expect(workflow.locator('.workflow-future-grid')).toContainText('Relationships & contracts')
  }

  await expectContained(page)
  if (isIphone) {
    await expectElementContained(page, 'section.workflow-workspace-page')
  } else {
    const viewportWidth = page.viewportSize()?.width ?? 0
    const workflowBox = await workflow.boundingBox()
    expect(workflowBox).not.toBeNull()
    expect(workflowBox!.width).toBeLessThanOrEqual(viewportWidth + 0.5)
  }

  if (!isIphone) {
    const summary = workflow.locator('.workflow-command-summary')
    const summaryShot = await summary.screenshot()
    await testInfo.attach(`workflow-summary-${testInfo.project.name}.png`, { body: summaryShot, contentType: 'image/png' })
    const groupsShot = await workflow.locator('.workflow-intelligence-block').screenshot()
    await testInfo.attach(`workflow-groups-${testInfo.project.name}.png`, { body: groupsShot, contentType: 'image/png' })
  }

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
