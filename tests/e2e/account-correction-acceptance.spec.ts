import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { signInForProject } from './auth.helpers'
import { formatDate } from '../../src/domain/labels'
import type { SystemDetail, SystemSummary } from '../../src/types/data'

test.use({ trace: 'off' })
test.setTimeout(300_000)
async function publicData<T>(page: Page, base: string, relative: string): Promise<T> {
  if (process.env.CANDIDATE_ROOT) return JSON.parse(await readFile(path.join(process.env.CANDIDATE_ROOT, relative), 'utf8')) as T
  const response = await page.request.get(new URL(relative, base).href)
  expect(response.ok()).toBe(true)
  return await response.json() as T
}

test('all five Account modes retain top navigation, expanded content and mobile containment', async ({ page }, info) => {
  const errors: string[] = [], measurements: unknown[] = []
  page.on('pageerror', error => errors.push(error.message))
  await signInForProject(page, info.project.name, '#/account/2000015564')
  const panel = page.locator('.account-profile-page .detail-panel'), tabs = panel.locator('.account-mode-tabs')
  await expect(tabs).toBeVisible({ timeout: 120_000 })
  for (const [mode, selector] of [['Summary', '.account-decision-summary'], ['Sales', '.sales-precall-pack'], ['Field', '.technician-field-pack'], ['Evidence', '.account-evidence-workspace'], ['History', '.account-unified-timeline']]) {
    await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
    await expect(panel.locator(selector)).toBeVisible({ timeout: 120_000 })
    await page.evaluate(() => window.scrollTo(0, 0))
    const navBox = await tabs.boundingBox(), bodyBox = await panel.locator(selector).boundingBox()
    expect(navBox).not.toBeNull(); expect(bodyBox).not.toBeNull()
    expect(navBox!.y + navBox!.height).toBeLessThanOrEqual(bodyBox!.y + 1)
    const width = page.viewportSize()!.width
    for (const button of await tabs.getByRole('button').all()) {
      const box = await button.boundingBox()
      expect(box).not.toBeNull(); expect(box!.x).toBeGreaterThanOrEqual(-1); expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1)
    }
    if (mode === 'Evidence') {
      const groups = panel.locator('.account-evidence-workspace > details')
      await expect(groups).toHaveCount(7)
      for (const group of await groups.all()) {
        expect(await group.getAttribute('open')).toBeNull()
        await group.locator(':scope > summary').click()
        await expect(group).toHaveAttribute('open', '')
      }
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await info.attach(`${mode}-full`, { body: await page.screenshot({ fullPage: true, animations: 'disabled' }), contentType: 'image/png' })
    await page.evaluate(() => window.scrollTo(0, Math.min(900, document.documentElement.scrollHeight - innerHeight)))
    const hits = await tabs.getByRole('button').evaluateAll(buttons => buttons.map(button => {
      const box = button.getBoundingClientRect(), x = box.left + box.width / 2, y = box.top + box.height / 2
      const target = document.elementFromPoint(x, y)
      return !!target && (button === target || button.contains(target))
    }))
    expect(hits).toEqual([true, true, true, true, true])
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
    expect(bodyWidth).toBeLessThanOrEqual(width + 1)
    measurements.push({ mode, navBox, bodyBox, hits, width, bodyWidth })
    await info.attach(`${mode}-scroll`, { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
  }
  await info.attach('mode-acceptance.json', { body: JSON.stringify({ errors, measurements }, null, 2), contentType: 'application/json' })
  expect(errors).toEqual([])
})

test('retained real accounts preserve all DOB records, HPD fields, provenance and current trigger evidence', async ({ page }, info) => {
  const base = info.project.use.baseURL as string
  const systems = await publicData<{ systems: SystemSummary[] }>(page, base, 'data/systems.json')
  const results: unknown[] = []
  for (const systemId of ['2000002585', '2000011123']) {
    const detail = await publicData<SystemDetail>(page, base, `data/details/20/${systemId}.json`)
    const row = systems.systems.find(item => item.system_id === systemId)!
    await signInForProject(page, info.project.name, `#/account/${systemId}`)
    const panel = page.locator('.account-profile-page .detail-panel'), tabs = panel.locator('.account-mode-tabs')
    await expect(tabs).toBeVisible({ timeout: 120_000 })
    const trigger = panel.locator('.account-decision-evidence-grid article').first()
    const signal = detail.signals.find(item => item.type === row.primary_signal)
    if (!row.recent_confirmed_violation && signal) {
      await expect(trigger).toContainText(signal.reason)
      if (signal.date) await expect(trigger).toContainText(formatDate(signal.date))
    }
    await info.attach(`${systemId}-Summary`, { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
    await tabs.getByRole('button', { name: /^Evidence/ }).click()
    const groups = panel.locator('.account-evidence-workspace > details')
    await expect(groups).toHaveCount(7, { timeout: 120_000 })
    const group = (title: string) => groups.filter({ has: page.locator('summary strong', { hasText: title }) })
    const projects = group('Project Activity')
    await projects.locator(':scope > summary').click()
    const now = projects.locator('.evidence-subsection').filter({ has: page.getByRole('heading', { name: 'DOB NOW project activity', exact: true }) })
    const expected = detail.dob_activity_history ?? []
    for (let batch = 1; batch < Math.ceil(expected.length / 20); batch++) await now.getByRole('button', { name: /show.*more.*filing/i }).click()
    const records = now.locator('.evidence-card-list > details')
    await expect(records).toHaveCount(expected.length)
    expect(await records.locator(':scope > summary strong').allTextContents()).toEqual(expected.map(record => record.job_filing_number ?? 'DOB filing'))
    await expect(now.getByRole('button', { name: /show.*more.*filing/i })).toHaveCount(0)
    if (expected.length) {
      await records.last().locator(':scope > summary').click()
      for (const label of ['Initial cost', 'Filing date', 'Current status date', 'First permit date', 'Approved date', 'Signoff date', 'Mechanical systems flag', 'Boiler equipment flag']) await expect(records.last().getByText(label, { exact: true })).toBeVisible()
      await info.attach(`${systemId}-last-DOB-record`, { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
    }
    const property = group('Property / Ownership')
    await property.locator(':scope > summary').click()
    if (detail.building_context) await expect(property.getByText('Lot area', { exact: true })).toBeVisible()
    for (const contact of detail.hpd_registration?.contacts ?? []) {
      if (contact.person_name) await expect(property).toContainText(contact.person_name)
      if (contact.corporation_name) await expect(property).toContainText(contact.corporation_name)
    }
    if (detail.hpd_registration?.last_registration_date) await expect(property).toContainText(formatDate(detail.hpd_registration.last_registration_date))
    const historical = group('Historical Evidence')
    await historical.locator(':scope > summary').click()
    await historical.locator('.evidence-provenance-details > summary').click()
    await expect(historical).toContainText(detail.metadata.rules_version)
    await expect(historical).toContainText(detail.metadata.priority_model_version)
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width + 1)
    results.push({ systemId, expectedDobRecords: expected.length, accessibleDobRecords: await records.count(), contactRows: detail.hpd_registration?.contacts.length, trigger: await trigger.textContent() })
  }
  await info.attach('source-parity-acceptance.json', { body: JSON.stringify(results, null, 2), contentType: 'application/json' })
})
