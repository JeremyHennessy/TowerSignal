import { mkdirSync, writeFileSync } from 'node:fs'
import { expect, test } from './fixtures'
import type { Page, TestInfo } from '@playwright/test'

const candidate = '18c21ea5f7e536fb94479ef8c8ac4065045597f4'
const productCode = 'c83a07d719e963efc9990b59e1a17ddb1705429c'

test.use({ trace: 'off' })
test.setTimeout(240_000)

async function releaseIdentity(page: Page) {
  expect(process.env.CANDIDATE_ROOT ?? '').toBe('')
  const response = await page.request.get('data/account-release.json')
  expect(response.ok()).toBe(true)
  const release = await response.json()
  expect(release.candidate_sha).toBe(candidate)
  expect(release.source_pages_run).toBe(35356884004)
  return release
}

async function capture(page: Page, info: TestInfo, name: string, states: unknown[]) {
  const folder = info.outputPath('supplement')
  mkdirSync(folder, { recursive: true })
  await page.evaluate(() => window.scrollTo(0, 0))
  await expect(page.locator('.loading-page,.fatal-state')).toHaveCount(0)
  const geometry = await page.evaluate(() => ({
    hash: location.hash, width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight,
    headings: Array.from(document.querySelectorAll('h1,h2,h3,h4')).filter(el => el.getClientRects().length).map(el => el.textContent),
    text: document.body.innerText,
  }))
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width + 2)
  expect(geometry.text.length).toBeGreaterThan(300)
  const stem = name.toLowerCase().replace(/[^a-z0-9]+/g, '-')
  const images = [stem + '.png']
  await page.screenshot({ path: `${folder}/${images[0]}`, scale: 'css', animations: 'disabled' })
  if (geometry.height < 24000) {
    images.push(stem + '-full.png')
    await page.screenshot({ path: `${folder}/${images[1]}`, fullPage: true, scale: 'css', animations: 'disabled' })
  } else {
    for (let y = page.viewportSize()!.height; y < geometry.height; y += page.viewportSize()!.height) {
      await page.evaluate(top => window.scrollTo(0, top), y)
      const file = `${stem}-${y}.png`
      await page.screenshot({ path: `${folder}/${file}`, scale: 'css', animations: 'disabled' })
      images.push(file)
    }
  }
  states.push({ name, hash: geometry.hash, images, geometry })
  writeFileSync(`${folder}/manifest.json`, JSON.stringify({ mode: 'ACTUAL_HOSTED_SUPPLEMENT', code_sha: productCode, verification_sha: process.env.GITHUB_SHA, application_candidate: candidate, project: info.project.name, states }, null, 2))
}

test('NYS account drill-through preserves the selected source equipment and accessible details', async ({ page }, info) => {
  const before = await releaseIdentity(page)
  const errors: string[] = [], states: unknown[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.evaluate(() => { location.hash = '#/nys' })
  const row = page.locator('table.nys-table tbody tr').first()
  await expect(row).toBeVisible({ timeout: 90_000 })
  const equipment = (await row.locator('td').nth(4).textContent())!.trim()
  expect(equipment.length).toBeGreaterThan(0)
  // The table explicitly exposes this keyboard interaction on every record.
  await row.focus()
  await row.press('Enter')
  await expect(page).toHaveURL(/#\/nys-account\/[^?]+/)
  await expect(page.locator('.detail-panel')).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.detail-panel')).toContainText(equipment)
  await expect(page.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await capture(page, info, 'NYS account selected equipment', states)
  for (const details of await page.locator('.detail-panel details').all()) {
    if (await details.getAttribute('open') === null) await details.locator(':scope > summary').click()
  }
  await capture(page, info, 'NYS account expanded source details', states)
  expect(errors).toEqual([])
  expect(await releaseIdentity(page)).toEqual(before)
})

test('225 Broadway matches the reported 1792 pixel desktop viewport in every Account mode', async ({ page }, info) => {
  test.skip(info.project.name === 'iphone', 'The native iPhone viewport is already covered by the main release suite.')
  await releaseIdentity(page)
  await page.setViewportSize({ width: 1792, height: 862 })
  await page.evaluate(() => { location.hash = '#/account/2000010998?view=sales' })
  const panel = page.locator('.account-profile-page .detail-panel')
  const tabs = panel.locator('.account-mode-tabs')
  await expect(tabs).toBeVisible({ timeout: 90_000 })
  const states: unknown[] = []
  for (const [mode, selector] of [['Sales', '.sales-precall-pack'], ['Summary', '.account-decision-summary'], ['Field', '.technician-field-pack'], ['Evidence', '.account-evidence-workspace'], ['History', '.account-unified-timeline']]) {
    await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
    await expect(panel.locator(selector)).toBeVisible({ timeout: 90_000 })
    await page.evaluate(() => window.scrollTo(0, 0))
    const a = (await tabs.boundingBox())!, b = (await panel.locator(selector).boundingBox())!
    expect(a.y + a.height).toBeLessThanOrEqual(b.y + 1)
    await capture(page, info, `225 Broadway 1792px ${mode}`, states)
  }
  await releaseIdentity(page)
})
