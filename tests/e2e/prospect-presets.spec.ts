import { expect, test } from './fixtures'
import { signInForProject } from './auth.helpers'
import { expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(180_000)

test('Prospect presets are URL-restorable and switching columns preserves filters', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/prospect?borough=Manhattan&preset=sales')
  await expect(page.getByRole('heading', { name: 'Prospect workspace' })).toBeVisible()
  const presets = page.getByRole('group', { name: 'Prospect table columns' })
  await expect(presets.getByRole('button', { name: 'Sales', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('Borough')).toHaveValue('Manhattan')
  await expect(page.locator('.account-table-card')).toHaveAttribute('data-prospect-preset', 'sales')
  await expect(page.getByRole('columnheader', { name: 'Observed firms' })).toBeVisible()

  await presets.getByRole('button', { name: 'Field', exact: true }).click()
  await expect(presets.getByRole('button', { name: 'Field', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('Borough')).toHaveValue('Manhattan')
  await expect(page).toHaveURL(/preset=field/)
  await expect(page).toHaveURL(/borough=Manhattan/)
  await expect(page.getByRole('columnheader', { name: 'Enforcement' })).toBeVisible()
  await expect(page.getByText('SWO complaint dispositions', { exact: false }).first()).toBeVisible()

  await presets.getByRole('button', { name: 'Timing', exact: true }).click()
  await expect(page.getByLabel('Borough')).toHaveValue('Manhattan')
  await expect(page).toHaveURL(/preset=timing/)
  await expect(page.getByRole('columnheader', { name: 'Timing signal' })).toBeVisible()
  await expectContained(page)
})

test('Prospect presets stay contained across supported desktop widths', async ({ page }, testInfo) => {
  test.skip(isIphoneProject(testInfo), 'Desktop width coverage is exercised by Chromium')
  await signInForProject(page, testInfo.project.name, '#/prospect?preset=timing')
  await expect(page.getByRole('heading', { name: 'Prospect workspace' })).toBeVisible()

  const presets = page.getByRole('group', { name: 'Prospect table columns' })
  const cases = [
    { name: 'Timing', header: 'Timing signal' },
    { name: 'Sales', header: 'Observed firms' },
    { name: 'Field', header: 'Enforcement' },
  ] as const

  for (const width of [1280, 1440, 1600]) {
    await page.setViewportSize({ width, height: 900 })
    for (const preset of cases) {
      await presets.getByRole('button', { name: preset.name, exact: true }).click()
      await expect(presets.getByRole('button', { name: preset.name, exact: true })).toHaveAttribute('aria-pressed', 'true')
      await expect(page.getByRole('columnheader', { name: preset.header })).toBeVisible()
      await expectContained(page)
      await expect.poll(async () => {
        const box = await page.locator('.account-table-card').boundingBox()
        return box?.width ?? 0
      }).toBeLessThanOrEqual(width + 0.5)
    }
  }
})

// The existing mobile design hides the Saved views rail below 780px.
// Preserve that UI; verify persistence in the supported desktop layout in
// both Chromium and WebKit. Other preset tests retain native phone coverage.
test.describe('Saved views in the supported desktop layout', () => {
  test.use({ viewport: { width: 1280, height: 900 }, screen: { width: 1280, height: 900 } })

test('Prospect saved views restore the active preset through the existing workflow state owner', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/prospect?borough=Queens&preset=field')
  await expect(page.getByRole('heading', { name: 'Prospect workspace' })).toBeVisible()

  const name = `Preset persistence ${testInfo.project.name} ${Date.now()}`
  await page.getByLabel('Saved view name').fill(name)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  const saved = page.getByRole('button', { name, exact: true })
  await expect(saved).toBeVisible()

  const presets = page.getByRole('group', { name: 'Prospect table columns' })
  await presets.getByRole('button', { name: 'Timing', exact: true }).click()
  await page.getByLabel('Borough').selectOption('Manhattan')
  await expect(presets.getByRole('button', { name: 'Timing', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('Borough')).toHaveValue('Manhattan')

  await saved.click()
  await expect(presets.getByRole('button', { name: 'Field', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('Borough')).toHaveValue('Queens')
  await expect(page).toHaveURL(/preset=field/)
  await expect(page).toHaveURL(/borough=Queens/)
  await expectContained(page)
})

})

test('Prospect shared links reject unknown preset values without changing filters', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/prospect?minScore=70&preset=not-a-preset')
  await expect(page.getByRole('heading', { name: 'Prospect workspace' })).toBeVisible()
  const presets = page.getByRole('group', { name: 'Prospect table columns' })
  await expect(presets.getByRole('button', { name: 'Timing', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('Minimum priority score')).toHaveValue('70')
  await expectContained(page)
})
