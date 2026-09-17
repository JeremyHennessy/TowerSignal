import { expect, test } from '@playwright/test'

const BRIDGE_URL = 'https://br-small-resonance-auw6h71b-authbridgeproof.compute.c-10.us-east-1.aws.neon.tech'
const DATA_API_URL = 'https://ep-nameless-brook-auxfp8jj.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'
const REFRESH_KEY = 'towersignal.workflow.bridge-refresh.v1'
const WATCHLIST_ID = 'arcny-demo-all-associated-sites'
const WATCHLIST_NAME = 'ArcNY Demo — All Associated Sites'

const accounts = [
  ['2000002133', 'Arc Companies / Arc Ventures office\nPrivate ArcNY research record. 655 Third Ave is the observed Arc office host building; this is not an ownership, tower-service, contract, or compliance claim.'],
  ['NYS-8615', 'International Corporate Center at Rye\nPrivate ArcNY research record outside the NYC public snapshot.'],
  ['arcny-site-s001', 'Solaria Riverdale\nPrivate site research record, not a cooling-tower registration.'],
  ['arcny-site-s003', 'Murray Hill Terrace\nPrivate site research record, not a cooling-tower registration.'],
  ['arcny-site-s004', 'West Village Multifamily\nPrivate site research record. Exact property identity is unresolved.'],
  ['arcny-site-s005', 'West Clinic of Memphis 3-office portfolio\nPrivate external research record outside the NYC market.'],
  ['arcny-site-s006', 'River Center\nPrivate historical research record. Current property identity remains unverified.'],
  ['arcny-site-s007', 'Atlantic City provisional Skyline/Skyview match\nPrivate provisional research record outside the NYC market.'],
  ['arcny-site-s008', '59 W 70\nPrivate site research record, not a cooling-tower registration.'],
  ['arcny-site-s009', '61 W 70\nPrivate site research record, not a cooling-tower registration.'],
  ['arcny-site-s010', '133 W 70\nPrivate site research record, not a cooling-tower registration.'],
] as const

async function seedArcny(page: import('@playwright/test').Page) {
  await page.evaluate(async ({ bridgeUrl, dataApiUrl, refreshKey, watchlistId, watchlistName, seedAccounts }) => {
    const refresh = window.sessionStorage.getItem(refreshKey)
    if (!refresh) throw new Error('Candidate did not retain sealed Workflow refresh credential')
    const session = await fetch(`${bridgeUrl}/session`, {
      method: 'POST',
      headers: { authorization: `Bearer ${refresh}`, 'content-type': 'application/json' },
      body: '{}',
      cache: 'no-store',
    })
    if (!session.ok) throw new Error(`Bridge session seed exchange failed ${session.status}: ${await session.text()}`)
    const sessionPayload = await session.json()
    const jwt = sessionPayload.token
    if (!jwt) throw new Error('Bridge session seed exchange returned no JWT')
    if (sessionPayload.refresh) window.sessionStorage.setItem(refreshKey, sessionPayload.refresh)
    const headers = { authorization: `Bearer ${jwt}`, 'content-type': 'application/json', prefer: 'return=representation' }

    const request = async (path: string, init: RequestInit = {}) => {
      const response = await fetch(`${dataApiUrl}/${path}`, { ...init, headers: { ...headers, ...(init.headers || {}) }, cache: 'no-store' })
      const text = await response.text()
      if (!response.ok) throw new Error(`Seed ${init.method || 'GET'} ${path} failed ${response.status}: ${text}`)
      return text ? JSON.parse(text) : null
    }

    const existingWatchlist = await request(`workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}&select=watchlist_id`)
    if (!existingWatchlist.length) await request('workflow_watchlists', { method: 'POST', body: JSON.stringify({ watchlist_id: watchlistId, name: watchlistName }) })

    for (const [systemId, note] of seedAccounts) {
      const existingAccount = await request(`workflow_accounts?system_id=eq.${encodeURIComponent(systemId)}&select=system_id`)
      const values = { status: 'monitor', note, next_action_date: null, updated_at: new Date().toISOString() }
      if (existingAccount.length) {
        await request(`workflow_accounts?system_id=eq.${encodeURIComponent(systemId)}`, { method: 'PATCH', body: JSON.stringify(values) })
      } else {
        await request('workflow_accounts', { method: 'POST', body: JSON.stringify({ system_id: systemId, ...values }) })
      }
      const membership = await request(`workflow_watchlist_members?watchlist_id=eq.${encodeURIComponent(watchlistId)}&system_id=eq.${encodeURIComponent(systemId)}&select=system_id`)
      if (!membership.length) await request('workflow_watchlist_members', { method: 'POST', body: JSON.stringify({ watchlist_id: watchlistId, system_id: systemId }) })
    }
  }, { bridgeUrl: BRIDGE_URL, dataApiUrl: DATA_API_URL, refreshKey: REFRESH_KEY, watchlistId: WATCHLIST_ID, watchlistName: WATCHLIST_NAME, seedAccounts: accounts })
}

test.setTimeout(180_000)

test('sealed session restores Workflow after full reload and preserves ArcNY external leads', async ({ page }, testInfo) => {
  const suffix = `${process.env.GITHUB_RUN_ID || Date.now()}-${testInfo.project.name}`.replace(/[^a-z0-9-]/gi, '-').toLowerCase()
  const email = `towersignal-bridge-${suffix}@example.com`
  const password = 'TowerSignal-E2E-2026!'

  await page.goto('./#/login', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Full name').fill('Bridge Candidate')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByText(email, { exact: true })).toBeVisible()

  const sealedRefresh = await page.evaluate(key => window.sessionStorage.getItem(key), REFRESH_KEY)
  expect(sealedRefresh?.length ?? 0).toBeGreaterThan(80)
  await seedArcny(page)

  // This is the critical #209 regression proof: reload destroys the module's
  // in-memory JWT. The app must restore via sealed refresh and get a new JWT.
  await page.evaluate(() => { window.location.hash = '#/workflow' })
  await page.reload({ waitUntil: 'networkidle' })
  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible()
  const watchlist = workflow.getByLabel('Workflow watchlist filter')
  await expect(watchlist.locator(`option[value="${WATCHLIST_ID}"]`)).toContainText(`${WATCHLIST_NAME} (11)`)
  await watchlist.selectOption(WATCHLIST_ID)
  const rows = workflow.locator('.workflow-command-table tbody tr')
  await expect(rows).toHaveCount(11)
  await expect(rows.filter({ hasText: '2000002133' }).first()).toContainText('655 Third Ave')
  await expect(workflow.locator('.workflow-command-table-card')).toContainText('Solaria Riverdale')

  const external = rows.filter({ hasText: 'Solaria Riverdale' }).first()
  await external.click()
  const inspector = workflow.locator('.workflow-account-inspector')
  await expect(inspector).toContainText('External / unverified research')
  await expect(inspector).toContainText('Not linked to current NYC market snapshot')
  await expect(inspector).toContainText('Not scored')
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

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)
  expect(overflow).toBe(false)

  await page.evaluate(() => { window.location.hash = '#/my-account' })
  await page.getByRole('button', { name: /sign out/i }).click()
  await page.reload({ waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  expect(await page.evaluate(key => window.sessionStorage.getItem(key), REFRESH_KEY)).toBeNull()
})
