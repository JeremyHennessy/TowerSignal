import type { Page } from '@playwright/test'
import { testCredentials } from './auth.helpers'

const DEFAULT_AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const DEFAULT_DATA_API_URL = 'https://ep-silent-moon-au2icaki.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'
const AUTH_URL = process.env.TOWERSIGNAL_WORKFLOW_AUTH_URL || DEFAULT_AUTH_URL
const DATA_API_URL = process.env.TOWERSIGNAL_WORKFLOW_DATA_API_URL || DEFAULT_DATA_API_URL

export const ARCNY_WATCHLIST_ID = 'arcny-demo-all-associated-sites'
export const ARCNY_WATCHLIST_NAME = 'ArcNY Demo — All Associated Sites'

type ArcnySeedAccount = {
  system_id: string
  note: string
}

const ARCNY_ACCOUNTS: ArcnySeedAccount[] = [
  {
    system_id: '2000002133',
    note: 'Arc Companies / Arc Ventures office\nPrivate ArcNY research record. 655 Third Ave is the observed Arc office host building; this is not an ownership, tower-service, contract, or compliance claim.',
  },
  {
    system_id: 'NYS-8615',
    note: 'International Corporate Center at Rye\nPrivate ArcNY research record. Exact NYS registry identity retained outside the NYC market; no NYC ownership, provider, contract, or compliance claim is inferred.',
  },
  {
    system_id: 'arcny-site-s001',
    note: 'Solaria Riverdale\nPrivate site research record, not a cooling-tower registration. Property identity and any ArcNY relationship require separate verification.',
  },
  {
    system_id: 'arcny-site-s003',
    note: 'Murray Hill Terrace\nPrivate site research record, not a cooling-tower registration. Property identity and any ArcNY relationship require separate verification.',
  },
  {
    system_id: 'arcny-site-s004',
    note: 'West Village Multifamily\nPrivate site research record. Exact property identity is unresolved; no ownership, tower, provider, contract, or compliance claim is inferred.',
  },
  {
    system_id: 'arcny-site-s005',
    note: 'West Clinic of Memphis 3-office portfolio\nPrivate external research record outside the NYC market. Site identity and any ArcNY relationship require verification.',
  },
  {
    system_id: 'arcny-site-s006',
    note: 'River Center\nPrivate historical research record. Current property identity and any ArcNY relationship remain unverified.',
  },
  {
    system_id: 'arcny-site-s007',
    note: 'Atlantic City provisional Skyline/Skyview match\nPrivate provisional research record outside the NYC market. The Skyline/Skyview identity is not treated as confirmed.',
  },
  {
    system_id: 'arcny-site-s008',
    note: '59 W 70\nPrivate site research record, not a cooling-tower registration. ArcNY relationship and service evidence require verification.',
  },
  {
    system_id: 'arcny-site-s009',
    note: '61 W 70\nPrivate site research record, not a cooling-tower registration. ArcNY relationship and service evidence require verification.',
  },
  {
    system_id: 'arcny-site-s010',
    note: '133 W 70\nPrivate site research record, not a cooling-tower registration. ArcNY relationship and service evidence require verification.',
  },
]

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

function cookiesFromResponse(response: Response): string {
  const values = typeof response.headers.getSetCookie === 'function'
    ? response.headers.getSetCookie()
    : [response.headers.get('set-cookie')].filter((value): value is string => Boolean(value))
  return values.map(value => value.split(';', 1)[0]).join('; ')
}

function matchesAuthHost(domain: string, authHost: string): boolean {
  const normalized = domain.replace(/^\./, '')
  return normalized === authHost || authHost.endsWith(`.${normalized}`)
}

async function jwtFromBrowserSession(page: Page): Promise<string | null> {
  const authHost = new URL(AUTH_URL).hostname
  const matching = (await page.context().cookies()).filter(cookie => matchesAuthHost(cookie.domain, authHost))
  if (!matching.length) return null
  const cookieHeader = matching.map(cookie => `${cookie.name}=${cookie.value}`).join('; ')
  const response = await fetch(`${AUTH_URL}/get-session`, {
    headers: { cookie: cookieHeader, origin: new URL(page.url()).origin },
  })
  if (!response.ok) return null
  return response.headers.get('set-auth-jwt')
}

async function signInJwt(page: Page, projectName: string): Promise<string> {
  const credentials = testCredentials(projectName)
  const origin = new URL(page.url()).origin
  let lastError = 'no response'
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const response = await fetch(`${AUTH_URL}/sign-in/email`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', origin },
      body: JSON.stringify({ email: credentials.email, password: credentials.password }),
      redirect: 'manual',
    })
    const text = await response.text()
    if (response.ok) {
      const cookies = cookiesFromResponse(response)
      assert(cookies, `Managed auth sign-in returned no session cookie for ${credentials.email}`)
      const session = await fetch(`${AUTH_URL}/get-session`, { headers: { cookie: cookies, origin } })
      const sessionText = await session.text()
      if (!session.ok) throw new Error(`/get-session failed ${session.status}: ${sessionText}`)
      const jwt = session.headers.get('set-auth-jwt')
      assert(jwt, 'Managed auth did not return set-auth-jwt for ArcNY fixture seeding')
      return jwt
    }
    lastError = `${response.status}: ${text}`
    if (response.status !== 429 || attempt === 3) break
    const retryAfter = Number(response.headers.get('retry-after') || 0)
    await new Promise(resolve => setTimeout(resolve, Math.max(2_000, retryAfter * 1_000)))
  }
  throw new Error(`Unable to sign in ephemeral Workflow user for ArcNY seed: ${lastError}`)
}

async function dataRequest(jwt: string, path: string, init: RequestInit = {}) {
  const response = await fetch(`${DATA_API_URL}/${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${jwt}`,
      'content-type': 'application/json',
      ...(init.headers || {}),
    },
  })
  const text = await response.text()
  if (!response.ok) throw new Error(`Workflow Data API ${init.method || 'GET'} ${path} failed ${response.status}: ${text}`)
  return text ? JSON.parse(text) : null
}

async function ensureWatchlist(jwt: string) {
  const query = `workflow_watchlists?watchlist_id=eq.${encodeURIComponent(ARCNY_WATCHLIST_ID)}&select=watchlist_id,name`
  const rows = await dataRequest(jwt, query) as Array<{ watchlist_id: string; name: string }>
  if (!rows.length) {
    await dataRequest(jwt, 'workflow_watchlists', {
      method: 'POST',
      headers: { prefer: 'return=representation' },
      body: JSON.stringify({ watchlist_id: ARCNY_WATCHLIST_ID, name: ARCNY_WATCHLIST_NAME }),
    })
    return
  }
  if (rows[0].name !== ARCNY_WATCHLIST_NAME) {
    await dataRequest(jwt, `workflow_watchlists?watchlist_id=eq.${encodeURIComponent(ARCNY_WATCHLIST_ID)}`, {
      method: 'PATCH',
      headers: { prefer: 'return=representation' },
      body: JSON.stringify({ name: ARCNY_WATCHLIST_NAME, updated_at: new Date().toISOString() }),
    })
  }
}

async function ensureAccount(jwt: string, account: ArcnySeedAccount) {
  const query = `workflow_accounts?system_id=eq.${encodeURIComponent(account.system_id)}&select=system_id`
  const rows = await dataRequest(jwt, query) as Array<{ system_id: string }>
  const values = { status: 'monitor', note: account.note, next_action_date: null, updated_at: new Date().toISOString() }
  if (rows.length) {
    await dataRequest(jwt, `workflow_accounts?system_id=eq.${encodeURIComponent(account.system_id)}`, {
      method: 'PATCH',
      headers: { prefer: 'return=representation' },
      body: JSON.stringify(values),
    })
  } else {
    await dataRequest(jwt, 'workflow_accounts', {
      method: 'POST',
      headers: { prefer: 'return=representation' },
      body: JSON.stringify({ system_id: account.system_id, ...values }),
    })
  }
}

async function ensureMembership(jwt: string, systemId: string) {
  const query = `workflow_watchlist_members?watchlist_id=eq.${encodeURIComponent(ARCNY_WATCHLIST_ID)}&system_id=eq.${encodeURIComponent(systemId)}&select=watchlist_id,system_id`
  const rows = await dataRequest(jwt, query) as Array<{ watchlist_id: string; system_id: string }>
  if (rows.length) return
  await dataRequest(jwt, 'workflow_watchlist_members', {
    method: 'POST',
    headers: { prefer: 'return=representation' },
    body: JSON.stringify({ watchlist_id: ARCNY_WATCHLIST_ID, system_id: systemId }),
  })
}

export async function seedArcnyWorkflowForProject(page: Page, projectName: string): Promise<void> {
  const jwt = await jwtFromBrowserSession(page) ?? await signInJwt(page, projectName)
  await ensureWatchlist(jwt)
  for (const account of ARCNY_ACCOUNTS) {
    await ensureAccount(jwt, account)
    await ensureMembership(jwt, account.system_id)
  }

  const watchlists = await dataRequest(jwt, `workflow_watchlists?watchlist_id=eq.${encodeURIComponent(ARCNY_WATCHLIST_ID)}&select=watchlist_id,name`) as Array<{ watchlist_id: string; name: string }>
  const accounts = await dataRequest(jwt, `workflow_accounts?system_id=in.(${ARCNY_ACCOUNTS.map(row => encodeURIComponent(row.system_id)).join(',')})&select=system_id,status,note,next_action_date`) as Array<{ system_id: string; status: string; note: string; next_action_date: string | null }>
  const memberships = await dataRequest(jwt, `workflow_watchlist_members?watchlist_id=eq.${encodeURIComponent(ARCNY_WATCHLIST_ID)}&select=watchlist_id,system_id`) as Array<{ watchlist_id: string; system_id: string }>

  assert(watchlists.length === 1 && watchlists[0].name === ARCNY_WATCHLIST_NAME, 'ArcNY seed did not persist the expected watchlist')
  assert(accounts.length === ARCNY_ACCOUNTS.length, `ArcNY seed persisted ${accounts.length}/${ARCNY_ACCOUNTS.length} account states`)
  assert(accounts.every(row => row.status === 'monitor' && row.next_action_date == null), 'ArcNY seed account state must be monitor with no next-action date')
  assert(memberships.length === ARCNY_ACCOUNTS.length, `ArcNY seed persisted ${memberships.length}/${ARCNY_ACCOUNTS.length} memberships`)
}
