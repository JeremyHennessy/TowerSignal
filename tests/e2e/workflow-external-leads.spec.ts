import { expect, test } from '@playwright/test'
import { signInFreshForProject } from './auth.helpers'
import { expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(180_000)

// Workflow state is private per user. Setup seeds this run's isolated RLS user,
// then the test performs a fresh real sign-in in the same browser context so
// desktop + iPhone prove remote persistence without relying on cross-context
// third-party auth-cookie restoration on GitHub Pages.
test('ArcNY watchlist preserves external research leads without fabricating market evidence', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInFreshForProject(page, testInfo.project.name, '#/workflow')

  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible()
  const watchlist = workflow.getByLabel('Workflow watchlist filter')
  await expect(watchlist.locator('option[value="arcny-demo-all-associated-sites"]')).toContainText('ArcNY Demo — All Associated Sites (11)')
  await watchlist.selectOption('arcny-demo-all-associated-sites')

  const rows = workflow.locator('.workflow-command-table tbody tr')
  await expect(rows).toHaveCount(11)
  // 2000002133 is a real current NYC system. Mapped accounts retain their public
  // TowerSignal identity in the table instead of replacing it with private-note
  // display text used only for external/unverified synthetic leads.
  const mapped = rows.filter({ hasText: '2000002133' }).first()
  await expect(mapped).toContainText('655 Third Ave')
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
