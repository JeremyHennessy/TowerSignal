import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.use({ trace: 'off' })
test.setTimeout(180_000)

test('diagnose precursor Prospect gate without changing application or private Workflow', async ({ page }, info) => {
  await signInForProject(page, info.project.name, '#/prospect?borough=Manhattan&preset=sales')
  const card = page.locator('.account-table-card')
  await expect(card).toHaveAttribute('data-prospect-preset', 'sales', { timeout: 90_000 })
  await card.scrollIntoViewIfNeeded()
  const headings = await page.locator('.account-table thead th').evaluateAll(elements => elements.map(el => {
    const s = getComputedStyle(el), b = el.getBoundingClientRect()
    return { text: el.textContent, innerText: (el as HTMLElement).innerText, role: el.getAttribute('role'), scope: el.getAttribute('scope'), display: s.display, visibility: s.visibility, textTransform: s.textTransform,
      box: { top: b.top, left: b.left, width: b.width, height: b.height } }
  }))
  const saved = await page.locator('.saved-views').evaluateAll(elements => elements.map(el => ({ text: el.textContent, display: getComputedStyle(el).display, html: el.outerHTML })))
  const roles = { headers: await page.getByRole('columnheader').count(), titleCase: await page.getByRole('columnheader', { name: 'Observed firms' }).count(), insensitive: await page.getByRole('columnheader', { name: /observed firms/i }).count(), cells: await page.getByRole('cell', { name: /observed firms/i }).count() }
  await info.attach('prospect-gate-diagnostic.json', { body: JSON.stringify({ url: page.url(), headings, saved, roles }, null, 2), contentType: 'application/json' })
  await info.attach('prospect-table', { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
})
