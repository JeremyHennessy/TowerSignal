import { devices, expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { installCandidateRoutes } from './candidate-routes'

test.setTimeout(300_000)

const provenance = JSON.parse(readFileSync('docs/marketing/demo-deck-20260922.json', 'utf8')) as {
  assets: { path: string; pdf_page: number; pixel_width: number; pixel_height: number; size_bytes: number; sha256: string }[]
}

test('public landing uses the complete original deck with responsive uncropped images', async ({ browser }, testInfo) => {
  const iphone = testInfo.project.name.includes('iphone')
  const widths = iphone ? [390, 320] : [1440, 1024, 768]
  const evidence = []
  for (const width of widths) {
    // A fresh device context per width avoids accepting WebKit resize-only captures
    // with a stale layout viewport or transparent bitmap.
    const context = await browser.newContext({
      ...(iphone ? devices['iPhone 13'] : devices['Desktop Chrome']),
      viewport: { width, height: 900 }, screen: { width, height: 900 },
      storageState: { cookies: [], origins: [] },
      baseURL: process.env.BASE_URL ?? 'http://127.0.0.1:4173/TowerSignal/',
    })
    try {
      const page = await context.newPage()
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await installCandidateRoutes(page)
      await page.goto('./', { waitUntil: 'domcontentloaded' })
      const landing = page.locator('.marketing-page.marketing-deck-page')
      await expect(landing).toBeVisible()
      await expect(landing.getByRole('heading', { level: 1 })).toHaveText('Find the buildings that need you next.')
      await expect(landing.locator('.marketing-deck-notice')).toContainText('not the current live dataset')
      const figures = landing.locator('.marketing-deck-figure')
      await expect(figures).toHaveCount(8)
      await expect(landing.locator('img[src$="-mobile.svg"]')).toHaveCount(0)
      await expect(landing.locator('.marketing-float-card, .marketing-browser')).toHaveCount(0)

      const rendered = []
      for (const asset of provenance.assets) {
        const figure = landing.locator(`[data-demo-page="${asset.pdf_page}"]`)
        const image = figure.locator('img')
        await image.scrollIntoViewIfNeeded()
        await expect(image).toBeVisible()
        await image.evaluate(async element => { await (element as HTMLImageElement).decode() })
        const geometry = await image.evaluate(element => {
          const image = element as HTMLImageElement
          const rect = image.getBoundingClientRect()
          return { src: image.currentSrc, naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight, width: rect.width, height: rect.height, left: rect.left, right: rect.right }
        })
        expect(geometry.naturalWidth).toBe(asset.pixel_width)
        expect(geometry.naturalHeight).toBe(asset.pixel_height)
        expect(Math.abs(geometry.width / geometry.height - asset.pixel_width / asset.pixel_height)).toBeLessThan(.005)
        expect(geometry.left).toBeGreaterThanOrEqual(0)
        expect(geometry.right).toBeLessThanOrEqual(width + 1)
        const expectedURL = new URL(asset.path.replace(/^public\//, ''), page.url()).href
        expect(geometry.src).toBe(expectedURL)
        const link = figure.locator('.marketing-deck-image-link')
        await expect(link).toHaveAttribute('href', new URL(expectedURL).pathname)
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
        await expect(link).toHaveAttribute('aria-label', /full size/)
        await expect(figure.locator('figcaption')).toContainText('September 2026 demo')
        if (width === widths[0]) {
          const bytes = await page.evaluate(async url => {
            const response = await fetch(url, { cache: 'no-store' })
            if (!response.ok) throw new Error(`Demo image HTTP ${response.status}`)
            const buffer = await response.arrayBuffer()
            const hash = await crypto.subtle.digest('SHA-256', buffer)
            return { size: buffer.byteLength, sha256: [...new Uint8Array(hash)].map(value => value.toString(16).padStart(2, '0')).join('') }
          }, expectedURL)
          expect(bytes.size).toBe(asset.size_bytes)
          expect(bytes.sha256).toBe(asset.sha256)
        }
        rendered.push(geometry)
      }
      const viewport = await page.evaluate(() => ({ innerWidth, scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }))
      expect(viewport.innerWidth).toBe(width)
      expect(viewport.clientWidth).toBe(width)
      expect(viewport.scrollWidth).toBeLessThanOrEqual(width + 1)
      expect(errors).toEqual([])
      evidence.push({ requestedWidth: width, ...viewport, images: rendered })
      await page.evaluate(() => window.scrollTo(0, 0))
      await expect(landing.locator('.marketing-hero h1')).toBeInViewport()
      await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
      await testInfo.attach(`marketing-hero-${width}.png`, { body: await page.screenshot({ animations: 'disabled', scale: 'css' }), contentType: 'image/png' })
      if (width === widths[0]) {
        await testInfo.attach(`marketing-page-${width}.png`, { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })
        await landing.locator('.marketing-nav-actions button').click()
        await expect(landing.locator('#book-demo h2')).toBeInViewport()
        await landing.getByLabel('Full name').fill('Demo Visitor')
        await landing.getByLabel('Work email').fill('demo@example.com')
        await landing.getByLabel('Company', { exact: true }).fill('Demo company')
        await landing.getByRole('button', { name: /Request a demo/ }).click()
        await expect(landing.getByRole('status')).toContainText('this request has not been sent')
        await landing.getByRole('link', { name: 'Log in to TowerSignal', exact: true }).click()
        await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
      }
    } finally { await context.close() }
  }
  await testInfo.attach(`marketing-geometry-${testInfo.project.name}.json`, { body: JSON.stringify(evidence, null, 2), contentType: 'application/json' })
})
