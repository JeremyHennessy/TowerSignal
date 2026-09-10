import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium, webkit, devices } from 'playwright'
import { expect } from '@playwright/test'

const mode = process.argv[2] ?? 'hosted'
assert(['baseline', 'candidate', 'hosted'].includes(mode))
const base = 'https://jeremyhennessy.github.io/TowerSignal/'
const output = path.resolve(process.env.FIRM_PROOF_OUTPUT ?? `firm-proof/${mode}`)
await fs.mkdir(output, { recursive: true })
const reports = []
const mime = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2' }
for (const family of ['desktop', 'iphone']) {
  const browser = await (family === 'iphone' ? webkit : chromium).launch()
  const context = await browser.newContext(family === 'iphone' ? devices['iPhone 13'] : { viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const errors = []
  const failures = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('response', response => { if (response.url().startsWith(base) && response.status() >= 400) failures.push(`${response.status()} ${response.url()}`) })
  try {
    if (mode === 'candidate') {
      const root = path.resolve('dist')
      await page.route(`${base}**`, async route => {
        const relative = decodeURIComponent(new URL(route.request().url()).pathname.slice('/TowerSignal/'.length)) || 'index.html'
        const target = path.resolve(root, relative)
        assert(target.startsWith(root + path.sep), 'Candidate request escaped artifact root')
        try { await route.fulfill({ status: 200, contentType: mime[path.extname(target)] ?? 'application/octet-stream', body: await fs.readFile(target) }) }
        catch (error) { if (error.code !== 'ENOENT') throw error; await route.fulfill({ status: 404, body: 'Not present in candidate artifact' }) }
      })
    }
    await page.goto(`${base}#/companies`, { waitUntil: 'networkidle' })
    await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
    const suffix = `${process.env.GITHUB_RUN_ID ?? Date.now()}-${process.env.GITHUB_RUN_ATTEMPT ?? 1}-${mode}-${family}`
    await page.getByRole('tab', { name: 'Create account', exact: true }).click()
    await page.getByLabel('Full name').fill('Companies release verification')
    await page.getByLabel('Email').fill(`towersignal-firms-${suffix}@example.com`)
    await page.getByLabel('Password', { exact: true }).fill('TowerSignal-E2E-2026!')
    await page.getByLabel('Confirm password').fill('TowerSignal-E2E-2026!')
    await page.getByRole('button', { name: 'Create account', exact: true }).click()
    await expect(page.getByRole('heading', { level: 1, name: mode === 'baseline' ? 'Companies' : 'Known companies & firms', exact: true })).toBeVisible({ timeout: 45000 })
    await expect(page.locator('.companies-table tbody tr').first()).toBeVisible({ timeout: 30000 })
    await page.screenshot({ path: path.join(output, `companies-${family}.png`) })
    await fs.writeFile(path.join(output, `companies-${family}.txt`), await page.locator('body').innerText())
    if (mode === 'baseline') { reports.push({ family, mode, heading: 'Companies', runtimeErrors: errors, firstPartyFailures: failures }); continue }
    await expect(page.locator('.known-firms-page table')).toHaveCount(1)
    const payload = await page.evaluate(async baseUrl => {
      const response = await fetch(`${baseUrl}data/known-firms.json`, { cache: 'no-store' })
      if (!response.ok) throw new Error(`Known firms HTTP ${response.status}`)
      return response.json()
    }, base)
    assert.equal(payload.firms.length, payload.summary.known_firm_count)
    assert(payload.firms.length > 50, 'Production table must contain more than one page')
    await expect(page.locator('.known-firms-table tbody tr')).toHaveCount(50)
    const before = await page.locator('.known-firms-table tbody tr').first().innerText()
    await page.getByRole('button', { name: /Next/ }).last().click()
    const after = await page.locator('.known-firms-table tbody tr').first().innerText()
    assert.notEqual(before, after, 'Pagination did not change rows')
    const firm = payload.firms.find(row => row.mapped_site_count > 0 && row.observed_site_count > 50 && row.observed_site_count < 500) ?? payload.firms.find(row => row.mapped_site_count > 0)
    assert(firm, 'No mapped firm exists')
    await page.getByLabel('Known firm search', { exact: true }).fill(firm.canonical_name)
    const row = page.locator('.known-firms-table tbody tr').filter({ hasText: firm.canonical_name }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: /Open/ }).click()
    await expect(page.getByRole('heading', { level: 1, name: firm.canonical_name, exact: true })).toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('region', { name: 'Known firm site relationship map', exact: true })).toBeVisible()
    await expect(page.locator('.firm-sites-table tbody tr').first()).toBeVisible()
    const headings = await page.locator('.firm-sites-table th').allTextContents()
    for (const text of ['Priority', 'Sampling', 'Contact', 'Activity']) assert(headings.some(value => value.includes(text)), `Missing site column ${text}`)
    await page.screenshot({ path: path.join(output, `firm-profile-${family}.png`) })
    await page.locator('.firm-site-map-grid').screenshot({ path: path.join(output, `firm-map-${family}.png`) })
    await page.locator('.firm-sites-table').evaluate(element => element.scrollIntoView({ block: 'start' }))
    await page.screenshot({ path: path.join(output, `firm-sites-${family}.png`) })
    await fs.writeFile(path.join(output, `firm-profile-${family}.txt`), await page.locator('body').innerText())
    const width = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: innerWidth }))
    assert(width.page <= width.viewport + 2, `Page overflows horizontally: ${JSON.stringify(width)}`)
    const account = page.locator('.firm-sites-table a[href^="#/account/"]').first()
    if (await account.count()) {
      await account.click()
      await expect(page).toHaveURL(/#\/account\//)
      await expect(page.locator('.account-profile-page')).toBeVisible()
    }
    assert.deepEqual(errors, [], 'Browser runtime errors')
    assert.deepEqual(failures, [], 'First-party asset or data failures')
    reports.push({ family, mode, knownFirmCount: payload.firms.length, firmId: firm.firm_id, firmName: firm.canonical_name, sites: firm.observed_site_count, mappedSites: firm.mapped_site_count, headings, width, runtimeErrors: errors, firstPartyFailures: failures })
  } catch (error) {
    await page.screenshot({ path: path.join(output, `failure-${family}.png`) }).catch(() => {})
    await fs.writeFile(path.join(output, `failure-${family}.txt`), await page.locator('body').innerText().catch(() => 'Unavailable'))
    reports.push({ family, mode, error: String(error), runtimeErrors: errors, firstPartyFailures: failures })
    process.exitCode = 1
  } finally { await browser.close() }
}
await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(reports, null, 2))
console.log(JSON.stringify(reports, null, 2))
