// Actual hosted NYC screenshots. Isolated audit identity; no business workflow writes.
import { chromium, webkit, devices } from '@playwright/test'
import { createHash, randomBytes } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'

const base = 'https://jeremyhennessy.github.io/TowerSignal/'
if (process.env.CANDIDATE_ROOT) throw new Error('Hosted audit cannot substitute candidate bytes')
const family = process.env.AUDIT_BROWSER === 'iphone' ? 'iphone' : 'desktop'
const root = `ui-audit/${family}`
await mkdir(root, { recursive: true })
const digest = text => createHash('sha256').update(text).digest('hex')
const slug = text => text.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 110)
const manifest = { mode: 'ACTUAL_HOSTED_NYC', base, browser: family, code_sha: process.env.GITHUB_SHA, started_at: new Date().toISOString(), states: [], failures: [], console_errors: [], http_errors: [] }
const save = () => writeFile(`${root}/manifest.json`, JSON.stringify(manifest, null, 2))
async function identity() {
  const fetchText = async path => {
    const response = await fetch(base + path + '?audit=' + Date.now(), { signal: AbortSignal.timeout(90_000) })
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`)
    return response.text()
  }
  const [html, metadata] = await Promise.all([fetchText('index.html'), fetchText('data/metadata.json')])
  return { html_sha256: digest(html), metadata_sha256: digest(metadata), data_generated_at: JSON.parse(metadata).generated_at, enforcement_available: JSON.parse(metadata).property_enforcement_cache_available === true }
}
const browser = await (family === 'iphone' ? webkit : chromium).launch()
const context = await browser.newContext(family === 'iphone' ? devices['iPhone 13'] : { viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 })
const page = await context.newPage()
const pending = new Set()
page.on('request', r => { if (r.url().startsWith(base + 'data/')) pending.add(r) })
page.on('requestfinished', r => pending.delete(r))
page.on('requestfailed', r => { pending.delete(r); if (r.url().startsWith(base)) manifest.failures.push({ request: r.url(), error: r.failure()?.errorText }) })
page.on('pageerror', e => manifest.console_errors.push(String(e)))
page.on('response', r => { if (r.status() >= 400 && r.url().startsWith(base)) manifest.http_errors.push({ url: r.url(), status: r.status() }) })
async function ready() {
  await page.waitForTimeout(500)
  const until = Date.now() + 90_000
  while (pending.size && Date.now() < until) await page.waitForTimeout(250)
  if (pending.size) throw new Error('Hosted data did not settle')
  await page.waitForFunction(() => document.body.innerText.length > 200 && !/Loading source-backed details/.test(document.body.innerText), null, { timeout: 60_000 })
  await page.waitForTimeout(400)
}
async function capture(name) {
  await ready()
  await page.evaluate(() => window.scrollTo(0, 0))
  const stem = `${String(manifest.states.length + 1).padStart(3, '0')}-${slug(name)}`
  const state = await page.evaluate(() => ({ hash: location.hash, title: document.title, text: document.body.innerText, headings: [...document.querySelectorAll('h1,h2,h3')].filter(e => e.getClientRects().length).map(e => e.textContent), height: document.documentElement.scrollHeight, width: innerWidth, scroll_width: document.documentElement.scrollWidth, controls: [...document.querySelectorAll('button,[role=tab],summary,select')].filter(e=>e.getClientRects().length).map(e=>({text:e.textContent,role:e.getAttribute('role'),class:e.className,parent_class:e.parentElement.className})) }))
  const images = [stem + '.png']
  await page.screenshot({ path: `${root}/${images[0]}`, scale: 'css', animations: 'disabled', timeout: 60_000 })
  if (state.height < 24000) {
    images.push(stem + '-full.png')
    await page.screenshot({ path: `${root}/${images[1]}`, fullPage: true, scale: 'css', animations: 'disabled', timeout: 60_000 })
  } else {
    for (let y = page.viewportSize().height; y < state.height; y += page.viewportSize().height) {
      await page.evaluate(top => window.scrollTo(0, top), y)
      const tile = `${stem}-y${y}.png`
      await page.screenshot({ path: `${root}/${tile}`, scale: 'css', animations: 'disabled' })
      images.push(tile)
    }
  }
  await writeFile(`${root}/${stem}.json`, JSON.stringify(state, null, 2))
  manifest.states.push({ name, hash: state.hash, captured_at: new Date().toISOString(), images, diagnostics: stem + '.json', width: state.width, scroll_width: state.scroll_width, height: state.height })
  await save()
  console.log('Captured ' + name)
}
async function captureTabs(name) {
  const seen = new Set()
  for (let step = 0; step < 100; step += 1) {
    // Fresh inventory after EVERY interaction. Nested/later groups first, before a parent hides them.
    const options = await page.evaluate(() => {
      const groups = [...document.querySelectorAll('[role=tablist],[class*=tabs],[class*=view-toggle],[class*=timeline-filters]')].filter(e => e.getClientRects().length && !e.closest('.reference-top-nav,.portal-navigation'))
      return groups.reverse().flatMap(group => [...group.querySelectorAll('button,[role=tab]')].filter(e => e.getClientRects().length && !e.disabled && e.closest('[role=tablist],[class*=tabs],[class*=view-toggle],[class*=timeline-filters]') === group).map(e => {
        const label = (e.getAttribute('aria-label') || e.textContent).trim()
        const key = `${group.getAttribute('aria-label') || group.className}|${label}`
        e.setAttribute('data-audit-tab', key)
        return { key, label }
      }))
    })
    const next = options.find(item => !seen.has(item.key) && !/^(create account|sign in|sign out)$/i.test(item.label))
    if (!next) return
    seen.add(next.key)
    try {
      const control = page.locator('[data-audit-tab]').filter({ hasText: next.label })
      const exact = page.locator(`[data-audit-tab=${JSON.stringify(next.key)}]`)
      if (await exact.count() !== 1) throw new Error('Ambiguous tab: ' + next.key + ' ' + await control.count())
      await exact.click({ timeout: 20_000 })
      await capture(name + ' - ' + next.label)
    } catch (e) { manifest.failures.push({ state: name + '/' + next.label, error: String(e) }); await save() }
  }
  throw new Error('Tab inventory exceeded bounded traversal')
}
async function visit(route, name) {
  try {
    await page.evaluate(hash => { location.hash = hash }, '#/' + route)
    await capture(name)
    await captureTabs(name)
  } catch (e) { manifest.failures.push({ state: name, error: String(e) }); await save() }
}
try {
  manifest.before = await identity()
  const topic = await fetch('https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page')
  if (topic.ok) await writeFile(`${root}/official-topic.html`, await topic.text())
  await page.goto(base, { waitUntil: 'domcontentloaded' })
  await capture('Marketing')
  await page.goto(base + '#/companies', { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true }).waitFor()
  await capture('Login')
  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await capture('Create account')
  await page.getByLabel('Full name').fill('NYC UI Audit')
  await page.getByLabel('Email').fill(`towersignal-audit-${process.env.GITHUB_RUN_ID}-${process.env.GITHUB_RUN_ATTEMPT || 1}-${family}@example.com`)
  const password = 'Ts!' + randomBytes(20).toString('hex')
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await page.getByRole('heading', { name: 'Known companies & firms', exact: true }).waitFor({ timeout: 60_000 })
  for (const route of ['home','prospect','monitor','map','opportunities','companies','water-quality','portfolios','workflow','source-health','my-account','nys','nys-changes']) await visit(route, route)
  for (const id of ['2000000660','2000015564','2000012577','2000002409','2000000006']) await visit('account/' + id, 'Account ' + id)
  for (const id of ['known-firm-4abb52cdffb968606f23','observed-company-69f2a028243abcb16658']) await visit('company/' + id, 'Firm ' + id)
  manifest.after = await identity()
  manifest.stable_served_baseline = manifest.before.html_sha256 === manifest.after.html_sha256 && manifest.before.metadata_sha256 === manifest.after.metadata_sha256
  manifest.completed_at = new Date().toISOString()
  if (!manifest.stable_served_baseline) manifest.failures.push({ error: 'Release changed during capture' })
} catch (e) {
  manifest.failures.push({ state: 'audit', error: String(e) })
  await page.screenshot({ path: root + '/failure.png', scale: 'css' }).catch(() => {})
} finally {
  await save()
  await browser.close()
}
console.log(JSON.stringify({ states: manifest.states.length, failures: manifest.failures, console_errors: manifest.console_errors, http_errors: manifest.http_errors, before: manifest.before, after: manifest.after }, null, 2))
if (manifest.failures.length || manifest.console_errors.length || manifest.http_errors.length) process.exitCode = 1
