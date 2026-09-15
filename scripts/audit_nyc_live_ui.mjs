// Read-only hosted NYC visual inventory. Never serves candidate/fixture bytes.
import { chromium, webkit, devices } from '@playwright/test'
import { createHash, randomBytes } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'

const base = process.env.BASE_URL || 'https://jeremyhennessy.github.io/TowerSignal/'
if (base !== 'https://jeremyhennessy.github.io/TowerSignal/' || process.env.CANDIDATE_ROOT) throw new Error('Audit must use the actual NYC GitHub Pages site')
const family = process.env.AUDIT_BROWSER === 'iphone' ? 'iphone' : 'desktop'
const root = `ui-audit/${family}`
await mkdir(root, { recursive: true })
const manifest = { mode: 'HOSTED_NOT_CANDIDATE', base, browser: family, audit_code_sha: process.env.GITHUB_SHA, started_at: new Date().toISOString(), states: [], failures: [], console_errors: [], http_errors: [], request_failures: [] }
const sha = text => createHash('sha256').update(text).digest('hex')
const slug = text => text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 120)
const safeUrl = input => { try { const u = new URL(input); return `${u.origin}${u.pathname}` } catch { return String(input) } }
let sequence = 0
let page
const pendingData = new Set()
async function save() { await writeFile(`${root}/manifest.json`, JSON.stringify(manifest, null, 2)) }
async function source(name, optional = false) {
  const response = await fetch(new URL(name, base), { cache: 'no-store', signal: AbortSignal.timeout(90_000) })
  if (optional && response.status === 404) return null
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`)
  const text = await response.text()
  return { sha256: sha(text), bytes: Buffer.byteLength(text), value: name.endsWith('.json') ? JSON.parse(text) : text }
}
async function identity() {
  const [html, metadata, release] = await Promise.all([source('index.html'), source('data/metadata.json'), source('workflow-ui-release.json', true)])
  return { html_sha256: html.sha256, metadata_sha256: metadata.sha256, data_generated_at: metadata.value.generated_at, normalized_system_count: metadata.value.normalized_system_count, enforcement_available: metadata.value.property_enforcement_cache_available === true, release: release?.value ?? null }
}
async function settle() {
  await page.waitForFunction(() => document.body.innerText.trim().length > 200, null, { timeout: 45_000 })
  await page.waitForTimeout(500)
  const deadline = Date.now() + 90_000
  while (pendingData.size && Date.now() < deadline) await page.waitForTimeout(250)
  if (pendingData.size) throw new Error('Hosted data requests did not settle within 90 seconds')
  await page.waitForTimeout(family === 'iphone' ? 1000 : 450)
}
async function capture(name, extra = {}) {
  const file = `${String(++sequence).padStart(3, '0')}-${slug(name)}`
  await settle()
  const diagnostics = await page.evaluate(() => ({
    hash: location.hash,
    headings: [...document.querySelectorAll('h1,h2,h3,h4')].filter(el => el.getClientRects().length).map(el => el.textContent.trim()),
    controls: [...document.querySelectorAll('button,[role="tab"],select,summary')].filter(el => el.getClientRects().length).map(el => ({ tag: el.tagName, role: el.getAttribute('role'), text: el.textContent.trim().slice(0, 220), label: el.getAttribute('aria-label'), class: el.className, parent_class: el.parentElement?.className })),
    width: innerWidth, scroll_width: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight, text: document.body.innerText,
    local_links: [...document.querySelectorAll('a[href]')].filter(el => el.getClientRects().length).map(el => ({ text: el.textContent.trim(), href: el.getAttribute('href') })).filter(link => link.href.startsWith('#')),
  }))
  await page.evaluate(() => window.scrollTo(0, 0))
  const images = [`${file}.png`]
  const opts = { animations: 'disabled', scale: 'css', timeout: 60_000 }
  await page.screenshot({ path: `${root}/${images[0]}`, ...opts })
  if (diagnostics.height <= 24000) {
    images.push(`${file}-full.png`)
    await page.screenshot({ path: `${root}/${images[1]}`, fullPage: true, ...opts })
  } else {
    const height = page.viewportSize().height
    for (let y = height; y < diagnostics.height; y += height) {
      await page.evaluate(top => window.scrollTo(0, top), y)
      const tile = `${file}-y${y}.png`
      await page.screenshot({ path: `${root}/${tile}`, ...opts })
      images.push(tile)
    }
    await page.evaluate(() => window.scrollTo(0, 0))
  }
  await writeFile(`${root}/${file}.json`, JSON.stringify(diagnostics, null, 2))
  manifest.states.push({ name, captured_at: new Date().toISOString(), hash: diagnostics.hash, headings: diagnostics.headings, width: diagnostics.width, scroll_width: diagnostics.scroll_width, height: diagnostics.height, images, diagnostics: `${file}.json`, ...extra })
  console.log(JSON.stringify({ state: name, hash: diagnostics.hash, screenshot_count: images.length, overflow: diagnostics.scroll_width > diagnostics.width + 2 }))
  await save()
}
async function tabInventory() {
  return page.evaluate(() => {
    document.querySelectorAll('[data-nyc-audit-tab]').forEach(el => el.removeAttribute('data-nyc-audit-tab'))
    const deny = /^(sign out|delete|remove|save|export|create|add|clear|next|previous|apply|cancel|close|open workspace)/i
    const groups = '[role="tablist"],[class*="tabs"],[class*="view-toggle"],[class*="view-switch"],[class*="segmented"],[class*="timeline-filters"]'
    return [...document.querySelectorAll('button,[role="tab"]')].filter(el => {
      if (!el.getClientRects().length || el.disabled) return false
      if (el.closest('.top-navigation,.portal-navigation,.top-nav,.portal-nav')) return false
      const label = (el.getAttribute('aria-label') || el.textContent || '').trim()
      return label && label.length <= 150 && !deny.test(label) && (el.getAttribute('role') === 'tab' || Boolean(el.closest(groups)))
    }).map((el, index) => {
      el.setAttribute('data-nyc-audit-tab', String(index))
      return { id: String(index), label: (el.getAttribute('aria-label') || el.textContent).trim(), role: el.getAttribute('role'), group: el.closest(groups)?.className || 'tab' }
    })
  })
}
async function tabs(routeName) {
  const seen = new Set()
  for (let pass = 0; pass < 3; pass += 1) {
    const inventory = await tabInventory()
    let visited = 0
    for (const item of inventory) {
      const key = `${item.group}:${item.label}`
      if (seen.has(key)) continue
      seen.add(key)
      try {
        const locator = page.locator(`[data-nyc-audit-tab="${item.id}"]`)
        if (await locator.count() !== 1 || !await locator.isVisible()) {
          manifest.failures.push({ state: `${routeName}/${item.label}`, error: 'Discovered tab no longer uniquely visible; not assumed covered' })
          continue
        }
        await locator.click({ timeout: 15_000 })
        await capture(`${routeName} - ${item.label}`, { tab: item, source: 'visible tab control' })
        visited += 1
      } catch (error) { manifest.failures.push({ state: `${routeName}/${item.label}`, error: String(error) }); await save() }
    }
    if (!visited) break
  }
}
async function navigate(route, name) {
  try {
    await page.evaluate(hash => { location.hash = hash }, `#/${route}`)
    await settle()
    await page.waitForFunction(() => !/Building the latest|Loading account detail|Loading source-backed details/.test(document.body.innerText), null, { timeout: 60_000 })
    await capture(name)
    await tabs(name)
  } catch (error) {
    manifest.failures.push({ state: name, error: String(error) })
    await page.screenshot({ path: `${root}/failure-${slug(name)}.png`, scale: 'css', timeout: 30_000 }).catch(() => {})
    await save()
  }
}
const browser = await (family === 'iphone' ? webkit : chromium).launch({ headless: true })
try {
  const context = await browser.newContext(family === 'iphone' ? { ...devices['iPhone 13'] } : { viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 })
  page = await context.newPage()
  page.setDefaultTimeout(25_000)
  page.on('request', request => { if (request.url().startsWith(`${base}data/`)) pendingData.add(request) })
  page.on('requestfinished', request => pendingData.delete(request))
  page.on('requestfailed', request => pendingData.delete(request))
  page.on('pageerror', error => manifest.console_errors.push({ hash: page.url().split('#')[1], error: String(error) }))
  page.on('response', response => { if (response.status() >= 400) manifest.http_errors.push({ url: safeUrl(response.url()), status: response.status() }) })
  page.on('requestfailed', request => manifest.request_failures.push({ url: safeUrl(request.url()), error: request.failure()?.errorText }))
  manifest.before = await identity()
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 60_000 })
  await capture('Marketing landing')
  await page.goto(`${base}#/companies`, { waitUntil: 'domcontentloaded', timeout: 60_000 })
  await page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true }).waitFor({ state: 'visible', timeout: 45_000 })
  await capture('Login')
  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await capture('Create account')
  const email = `towersignal-audit-${process.env.GITHUB_RUN_ID || Date.now()}-${family}@example.com`
  const password = `Ts!${randomBytes(20).toString('hex')}`
  await page.getByLabel('Full name').fill('NYC UI Audit')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await page.getByRole('heading', { name: 'Known companies & firms', exact: true }).waitFor({ state: 'visible', timeout: 60_000 })
  const systems = (await source('data/systems.json')).value.systems
  for (const [route, name] of [
    ['home', 'Home'], ['prospect', 'Prospect'], ['monitor', 'Monitor'], ['map', 'Map'],
    ['opportunities', 'Opportunities'], ['companies', 'Companies'], ['water-quality', 'Water Quality'],
    ['portfolios', 'Portfolios'], ['workflow', 'Workflow'], ['source-health', 'Source Health'], ['my-account', 'My Account'],
  ]) await navigate(route, name)
  const representatives = [
    ['Enforcement', systems.find(row => row.hpd_open_violation_count > 0 && row.stop_work_order_event_count > 0)],
    ['No contact', systems.find(row => Number(row.hpd_contact_count ?? 0) === 0)],
    ['Institutional', systems.find(row => row.cms_institutional_facility_count > 0)],
    ['Multi tower', systems.find(row => row.active_equipment >= 5)],
    ['Recovered BBL', systems.find(row => String(row.bbl_identity_status || '').includes('RECOVER'))],
  ]
  const visited = new Set()
  for (const id of ['2000000660', '2000015564', '2000012577']) {
    if (!systems.some(row => row.system_id === id)) continue
    visited.add(id)
    await navigate(`account/${id}`, `Account ${id}`)
  }
  for (const [kind, row] of representatives) {
    if (!row || visited.has(row.system_id)) continue
    visited.add(row.system_id)
    await navigate(`account/${row.system_id}`, `Account ${kind} ${row.system_id}`)
  }
  for (const id of ['known-firm-4abb52cdffb968606f23', 'observed-company-69f2a028243abcb16658']) await navigate(`company/${id}`, `Firm ${id}`)
  manifest.after = await identity()
  manifest.stable_served_baseline = manifest.before.html_sha256 === manifest.after.html_sha256 && manifest.before.metadata_sha256 === manifest.after.metadata_sha256
  manifest.completed_at = new Date().toISOString()
  await save()
  console.log(JSON.stringify({ captured_states: manifest.states.length, failures: manifest.failures.length, console_errors: manifest.console_errors.length, stable_served_baseline: manifest.stable_served_baseline, before: manifest.before, after: manifest.after }, null, 2))
  if (!manifest.stable_served_baseline || manifest.failures.length) process.exitCode = 1
} catch (error) {
  manifest.failures.push({ state: 'audit', error: String(error) })
  if (page) {
    await writeFile(`${root}/failure.txt`, await page.locator('body').innerText().catch(() => 'No body')).catch(() => {})
    await page.screenshot({ path: `${root}/failure.png`, scale: 'css', timeout: 30_000 }).catch(() => {})
  }
  await save()
  console.error(String(error))
  process.exitCode = 1
} finally { await browser.close() }
