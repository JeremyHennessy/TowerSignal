import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(180_000)

// ArcNY demo acceptance is intentionally deferred from the active release sequence.
// Keep the scenario in the suite as documentation, but do not block unrelated releases
// on a private watchlist fixture that is outside the current acceptance scope.
test('ArcNY watchlist preserves external research leads without fabricating market evidence', async ({ page }, testInfo) => {
  test.skip(true, 'ArcNY demo task deferred by release decision; not part of the active release acceptance gate')
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/workflow')

  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible()
  const watchlist = workflow.getByLabel('Workflow watchlist filter')
  await expect(watchlist.locator('option[value="arcny-demo-all-associated-sites"]')).toContainText('ArcNY Demo — All Associated Sites (11)')
  await watchlist.selectOption('arcny-demo-all-associated-sites')

  const rows = workflow.locator('.workflow-command-table tbody tr')
  await expect(rows).toHaveCount(11)
  await expect(workflow.locator('.workflow-command-table-card')).toContainText('Arc Companies / Arc Ventures office')
  await expect(workflow.locator('.workflow-command-table-card')).toContainText('International Corporate Center at Rye')
  await expect(workflow.locator('.workflow-command-table-card')).toContainText('Solaria Riverdale')
  await expect(workflow.locator('.workflow-command-table-card')).toContainText('West Clinic of Memphis')

  const external = rows.filter({ hasText: 'Solaria Riverdale' }).first()
  await external.click()
  const inspector = workflow.locator('.workflow-account-inspector')
  await expect(inspector).toContainText('External / unverified research')
  await expect(inspector).toContainText('Not linked to current NYC market snapshot')
  await expect(inspector).toContainText('Not scored')
  await expect(inspector).toContainText('Private site research record, not a cooling-tower registration.')
  await expect(inspector.getByRole('button', { name: 'Open full account →' })).toHaveCount(0)

  await workflow.getByRole('button', { name: 'Map', exact: true }).click()
  await expect(workflow.locator('.workflow-command-map')).toContainText('10 external / unverified research leads not plotted')
  await expect(workflow.locator('.workflow-command-map')).toContainText('1 mapped records')
  await workflow.getByRole('button', { name: 'Table', exact: true }).click()
  await expect(rows).toHaveCount(11)

  await workflow.getByRole('tab', { name: /Changes/ }).click()
  await expect(workflow.locator('.workflow-command-table-card')).toContainText('source changes')
  await workflow.getByRole('tab', { name: /Actions/ }).click()
  await expect(workflow.locator('.workflow-command-tabs')).toContainText('Actions')

  await expectContained(page)
})
