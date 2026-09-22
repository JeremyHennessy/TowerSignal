import { mkdir, writeFile } from 'node:fs/promises'
import { expect, test } from './fixtures'

test('Source Health uses one linked first column, preserves every source and stays contained', async ({ page }, testInfo) => {
  test.setTimeout(180_000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  if (testInfo.project.name === 'desktop-chromium') await page.setViewportSize({ width: 1792, height: 1000 })
  await page.evaluate(() => { window.location.hash = '#/source-health' })
  await expect(page.getByRole('heading', { name: 'Source Health & Coverage', exact: true })).toBeVisible()
  await expect(page.locator('#source-health-monitoring tbody tr')).toHaveCount(12)
  await expect(page.locator('#source-health-datasets tbody tr')).toHaveCount(20)
  await expect(page.locator('#source-health-procurement tbody tr').first()).toBeVisible()
  const tables = ['diagnostics', 'enforcement', 'refresh', 'monitoring', 'datasets', 'procurement']
  const rowsByTable: Record<string, number> = {}
  for (const id of tables) {
    const table = page.locator(`#source-health-${id} table`)
    expect(await table.locator('thead th').first().innerText()).toMatch(/links/i)
    const rows = table.locator('tbody tr')
    rowsByTable[id] = await rows.count()
    expect(rowsByTable[id]).toBeGreaterThan(0)
    expect(await rows.evaluateAll(elements => elements.every(row => {
      const first = row.querySelector('td:first-child')
      return first && first.querySelectorAll('a.source-health-link').length > 0
        && first.querySelectorAll('a').length === row.querySelectorAll('a').length
        && first.querySelector('strong a') === null
    }))).toBe(true)
  }
  expect(rowsByTable.refresh).toBe(8)
  const externalLinks = await page.locator('.source-health-page a.source-health-link').evaluateAll(links => links.map(link => ({ href: link.getAttribute('href') || '', rel: link.getAttribute('rel') || '' })))
  expect(externalLinks.every(link => (link.href.startsWith('https://') || link.href.startsWith('/TowerSignal/data/')) && link.rel.includes('noopener'))).toBe(true)

  await page.getByRole('button', { name: 'Publisher directory', exact: true }).click()
  const directory = page.locator('#source-health-directory')
  await expect(directory).toHaveAttribute('open', '')
  const sourceUrls = await page.evaluate(async () => {
    const response = await fetch(new URL('data/systems.json', window.location.href))
    if (!response.ok) throw new Error(`systems HTTP ${response.status}`)
    const data = await response.json()
    return data.metadata.sources.map((source: { url: string }) => source.url).filter((url: string) => url?.startsWith('https://')) as string[]
  })
  const directoryUrls = await directory.locator('a').evaluateAll(links => links.map(link => link.getAttribute('href')))
  expect(sourceUrls.every(url => directoryUrls.includes(url))).toBe(true)
  const search = page.getByLabel('Find a publisher or dataset')
  await search.fill('y4fw-iqfr')
  await expect(directory.locator('tbody tr')).toHaveCount(1)
  await expect(directory).toContainText('NYC Cooling Tower Registrations')
  await search.fill('source-that-does-not-exist')
  await expect(directory).toContainText('No matching sources.')
  await search.fill('')
  await expect(directory.locator('tbody tr')).toHaveCount(directoryUrls.length)
  expect(await page.evaluate(() => window.location.hash)).toBe('#/source-health')

  const reports = await page.locator('#source-health-datasets a').evaluateAll(links => links.map(link => (link as HTMLAnchorElement).href))
  for (const url of reports) {
    const response = await page.request.head(url)
    expect(response.ok(), `Published dataset link ${url}: ${response.status()}`).toBe(true)
  }
  await mkdir('source-health-proof', { recursive: true })
  const stage = process.env.CANDIDATE_ROOT ? 'candidate' : 'hosted'
  const prefix = `source-health-proof/${stage}-${testInfo.project.name}-layout`
  await directory.screenshot({ path: `${prefix}-directory.png` })
  await directory.locator('summary').click()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: `${prefix}-top.png` })
  for (const id of tables) {
    const section = page.locator(`#source-health-${id}`)
    await section.scrollIntoViewIfNeeded()
    const scroll = section.locator('.reference-table-scroll').first()
    await scroll.focus()
    await expect(scroll).toBeFocused()
    const geometry = await scroll.evaluate(el => {
      const first = el.querySelector('tbody td:first-child')!
      const left = first.getBoundingClientRect().left
      el.scrollLeft = Math.min(250, el.scrollWidth - el.clientWidth)
      const after = first.getBoundingClientRect().left
      return { left, after, client: el.clientWidth, width: el.scrollWidth }
    })
    expect(Math.abs(geometry.after - geometry.left)).toBeLessThanOrEqual(2)
    await scroll.evaluate(el => { el.scrollLeft = 0 })
    await section.screenshot({ path: `${prefix}-${id}.png` })
  }
  if (testInfo.project.name === 'iphone') {
    const sizes = await page.locator('.source-health-page .source-health-link:visible').evaluateAll(links => links.map(link => link.getBoundingClientRect().height))
    expect(sizes.length).toBeGreaterThan(0)
    expect(sizes.every(height => height >= 44)).toBe(true)
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  expect(errors).toEqual([])
  await writeFile(`${prefix}-verification.json`, JSON.stringify({ rowsByTable, metadataUrls: sourceUrls.length, directoryLinks: directoryUrls.length, publishedDatasets: reports.length, overflow, errors }, null, 2))
})
