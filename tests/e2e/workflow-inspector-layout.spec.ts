import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectContained, isIphoneProject } from './iphone.helpers'

const desktopWidths = [2048, 1600, 1440, 1280, 1024]

async function seedWorkflowAccount(page: import('@playwright/test').Page, projectName: string) {
  await signInForProject(page, projectName, '#/account/2000015564')
  const section = page.locator('section.workflow-account-section')
  await expect(section).toBeVisible()
  await section.getByLabel('Status').selectOption('investigate')
  await section.getByLabel('Private note').fill('Review roof, compliance, ownership and watchlist evidence before the next outreach. Keep this note wrapped inside the inspector.')
  await section.getByRole('button', { name: 'Save workflow state', exact: true }).click()
  await expect(section.getByText('Saved', { exact: true })).toBeVisible()
}

async function assertWorkspaceGeometry(page: import('@playwright/test').Page, stacked: boolean) {
  const layout = await page.evaluate(() => {
    const rect = (selector: string) => {
      const element = document.querySelector(selector)
      if (!element) return null
      const box = element.getBoundingClientRect()
      return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height }
    }
    const inspector = document.querySelector('.workflow-account-inspector') as HTMLElement | null
    const boundary = document.querySelector('.workflow-inspector-boundary') as HTMLElement | null
    return {
      viewport: document.documentElement.clientWidth,
      pageScrollWidth: document.documentElement.scrollWidth,
      grid: rect('.workflow-command-grid'),
      primary: rect('.workflow-command-primary'),
      inspector: rect('.workflow-account-inspector'),
      tableCard: rect('.workflow-command-table-card'),
      tableScroll: rect('.workflow-command-table-card .table-scroll'),
      inspectorScrollWidth: inspector?.scrollWidth ?? 0,
      inspectorClientWidth: inspector?.clientWidth ?? 0,
      inspectorOverflowX: inspector ? getComputedStyle(inspector).overflowX : '',
      boundaryFontSize: boundary ? Number.parseFloat(getComputedStyle(boundary).fontSize) : 0,
      boundaryLineHeight: boundary ? getComputedStyle(boundary).lineHeight : '',
    }
  })
  expect(layout.pageScrollWidth).toBeLessThanOrEqual(layout.viewport + 2)
  expect(layout.grid).not.toBeNull()
  expect(layout.primary).not.toBeNull()
  expect(layout.inspector).not.toBeNull()
  expect(layout.inspector!.left).toBeGreaterThanOrEqual(layout.grid!.left - 1)
  expect(layout.inspector!.right).toBeLessThanOrEqual(layout.grid!.right + 1)
  expect(layout.inspectorScrollWidth).toBeLessThanOrEqual(layout.inspectorClientWidth + 2)
  expect(layout.boundaryFontSize).toBeLessThanOrEqual(10)
  if (layout.tableCard) expect(layout.tableCard.right).toBeLessThanOrEqual(layout.primary!.right + 1)
  if (layout.tableScroll) expect(layout.tableScroll.right).toBeLessThanOrEqual(layout.primary!.right + 1)
  if (stacked) {
    expect(layout.inspector!.top).toBeGreaterThanOrEqual(layout.primary!.bottom - 1)
  } else {
    expect(layout.primary!.right).toBeLessThanOrEqual(layout.inspector!.left - 8)
  }
}

test('Workflow Account Inspector stays contained through selections, views and desktop breakpoints', async ({ page }, testInfo) => {
  test.skip(isIphoneProject(testInfo), 'Desktop breakpoint coverage runs in Chromium; iPhone has a dedicated test.')
  test.setTimeout(300_000)
  await seedWorkflowAccount(page, testInfo.project.name)
  await page.evaluate(() => { location.hash = '#/workflow' })
  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible()

  for (const width of desktopWidths) {
    await page.setViewportSize({ width, height: 1000 })
    await expect(workflow.getByRole('heading', { name: 'Workflow workspace', exact: true })).toBeVisible()
    await workflow.getByRole('tab', { name: /^Accounts/ }).click()
    await workflow.getByRole('button', { name: 'Table', exact: true }).click()
    const row = workflow.locator('.workflow-command-table tbody tr', { hasText: '16 E 39TH ST' }).first()
    await expect(row).toBeVisible()
    await row.click()

    const inspector = workflow.locator('.workflow-account-inspector')
    await expect(inspector).toContainText('16 E 39TH ST')
    await expect(inspector).toContainText('Investigate')
    await expect(inspector).toContainText('Review roof, compliance, ownership')
    await expect(inspector.getByRole('button', { name: 'Open full account →', exact: true })).toBeVisible()
    await expect(inspector.locator('.workflow-inspector-boundary')).toBeVisible()
    await assertWorkspaceGeometry(page, width <= 1280)

    const headers = workflow.locator('.workflow-command-table:not(.workflow-change-table):not(.workflow-actions-table) thead th')
    await expect(headers).toHaveCount(10)
    const widths = await headers.evaluateAll(nodes => nodes.map(node => Math.round(node.getBoundingClientRect().width)))
    expect(widths[0]).toBeLessThan(widths[1])
    expect(widths[8]).toBeGreaterThan(widths[9])

    for (const view of ['Map + table', 'Map'] as const) {
      await workflow.getByRole('button', { name: view, exact: true }).click()
      await assertWorkspaceGeometry(page, width <= 1280)
    }
    await workflow.getByRole('button', { name: 'Table', exact: true }).click()

    await page.evaluate(() => window.scrollTo(0, 0))
    await testInfo.attach(`workflow-selected-${width}.png`, { body: await page.screenshot({ scale: 'css', fullPage: true, animations: 'disabled' }), contentType: 'image/png' })
  }

  await workflow.getByRole('tab', { name: /^Changes/ }).click()
  await expect(workflow.locator('.workflow-change-table')).toBeVisible()
  await workflow.locator('.workflow-change-table tbody tr').first().click()
  await assertWorkspaceGeometry(page, true)

  await workflow.getByRole('tab', { name: /^Actions/ }).click()
  const actionRows = workflow.locator('.workflow-actions-table tbody tr')
  if (await actionRows.count()) {
    await actionRows.first().click()
    await expect(workflow.locator('.workflow-account-inspector')).toContainText('Open full account')
  }
  await assertWorkspaceGeometry(page, true)

  const toolbox = workflow.locator('details.workflow-command-toolbox')
  await toolbox.locator('summary').click()
  await expect(toolbox).toHaveAttribute('open', '')
  const coverage = workflow.locator('details.workflow-coverage-details')
  await coverage.locator('summary').click()
  await expect(coverage).toHaveAttribute('open', '')
  await expectContained(page)
  await testInfo.attach('workflow-expanded-supporting-sections.png', { body: await page.screenshot({ scale: 'css', fullPage: true, animations: 'disabled' }), contentType: 'image/png' })
})

test('Workflow inspector and table stack without page overflow on iPhone', async ({ page }, testInfo) => {
  test.skip(!isIphoneProject(testInfo), 'iPhone-only containment regression')
  test.setTimeout(300_000)
  await seedWorkflowAccount(page, testInfo.project.name)
  await page.evaluate(() => { location.hash = '#/workflow' })
  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible()
  await workflow.getByRole('tab', { name: /^Accounts/ }).click()
  await workflow.getByRole('button', { name: 'Table', exact: true }).click()
  const row = workflow.locator('.workflow-command-table tbody tr', { hasText: '16 E 39TH ST' }).first()
  await row.scrollIntoViewIfNeeded()
  await row.click()
  const inspector = workflow.locator('.workflow-account-inspector')
  await inspector.scrollIntoViewIfNeeded()
  await expect(inspector).toContainText('16 E 39TH ST')
  await expect(inspector.getByRole('button', { name: 'Open full account →', exact: true })).toBeVisible()
  await assertWorkspaceGeometry(page, true)
  await expectContained(page)
  await testInfo.attach('workflow-inspector-iphone.png', { body: await page.screenshot({ scale: 'css', fullPage: true, animations: 'disabled' }), contentType: 'image/png' })
})
