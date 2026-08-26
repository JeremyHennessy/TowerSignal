const authUrl = process.env.TOWERSIGNAL_WORKFLOW_AUTH_URL
const dataApiUrl = process.env.TOWERSIGNAL_WORKFLOW_DATA_API_URL

if (!authUrl || !dataApiUrl) {
  throw new Error('TOWERSIGNAL_WORKFLOW_AUTH_URL and TOWERSIGNAL_WORKFLOW_DATA_API_URL are required')
}

const origin = 'http://localhost:5173'
const runId = process.env.GITHUB_RUN_ID || `${Date.now()}`
const nonce = `${runId}-${Math.random().toString(36).slice(2, 10)}`
const password = `Ts-${nonce}-Aa9!`
const email = `towersignal-workflow-${nonce}@example.com`
const otherEmail = `towersignal-isolation-${nonce}@example.com`
const watchlistId = `e2e-${nonce}`
const systemId = `E2E-${nonce}`

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function cookiesFrom(response) {
  const values = typeof response.headers.getSetCookie === 'function'
    ? response.headers.getSetCookie()
    : [response.headers.get('set-cookie')].filter(Boolean)
  return values.map(value => value.split(';', 1)[0]).join('; ')
}

async function authPost(path, body) {
  const response = await fetch(`${authUrl}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', origin },
    body: JSON.stringify(body),
    redirect: 'manual',
  })
  const text = await response.text()
  if (!response.ok) throw new Error(`${path} failed ${response.status}: ${text}`)
  return { cookies: cookiesFrom(response), body: text ? JSON.parse(text) : null }
}

async function jwtFrom(cookies) {
  const response = await fetch(`${authUrl}/get-session`, {
    headers: { cookie: cookies, origin },
  })
  const text = await response.text()
  if (!response.ok) throw new Error(`/get-session failed ${response.status}: ${text}`)
  const jwt = response.headers.get('set-auth-jwt')
  assert(jwt, 'Managed Better Auth did not return set-auth-jwt')
  return jwt
}

async function dataRequest(jwt, path, init = {}) {
  const response = await fetch(`${dataApiUrl}/${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${jwt}`,
      'content-type': 'application/json',
      ...(init.headers || {}),
    },
  })
  const text = await response.text()
  if (!response.ok) throw new Error(`Data API ${init.method || 'GET'} ${path} failed ${response.status}: ${text}`)
  return text ? JSON.parse(text) : null
}

async function signUp(emailValue) {
  const result = await authPost('/sign-up/email', {
    email: emailValue,
    password,
    name: 'TowerSignal workflow verifier',
    callbackURL: origin,
  })
  assert(result.cookies, `No session cookie returned for ${emailValue}`)
  return { cookies: result.cookies, jwt: await jwtFrom(result.cookies) }
}

async function signIn(emailValue) {
  const result = await authPost('/sign-in/email', { email: emailValue, password })
  assert(result.cookies, `No sign-in cookie returned for ${emailValue}`)
  return { cookies: result.cookies, jwt: await jwtFrom(result.cookies) }
}

const first = await signUp(email)
await dataRequest(first.jwt, 'workflow_watchlists', {
  method: 'POST',
  headers: { prefer: 'return=representation' },
  body: JSON.stringify({ watchlist_id: watchlistId, name: 'CI persistence proof' }),
})
await dataRequest(first.jwt, 'workflow_accounts', {
  method: 'POST',
  headers: { prefer: 'return=representation' },
  body: JSON.stringify({ system_id: systemId, status: 'follow-up', note: 'cross-session proof', next_action_date: '2026-09-15' }),
})
await dataRequest(first.jwt, 'workflow_watchlist_members', {
  method: 'POST',
  headers: { prefer: 'return=representation' },
  body: JSON.stringify({ watchlist_id: watchlistId, system_id: systemId }),
})

const secondSession = await signIn(email)
const watchlists = await dataRequest(secondSession.jwt, `workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}&select=watchlist_id,name`)
const accounts = await dataRequest(secondSession.jwt, `workflow_accounts?system_id=eq.${encodeURIComponent(systemId)}&select=system_id,status,note,next_action_date`)
const memberships = await dataRequest(secondSession.jwt, `workflow_watchlist_members?system_id=eq.${encodeURIComponent(systemId)}&select=watchlist_id,system_id`)
assert(watchlists.length === 1 && watchlists[0].name === 'CI persistence proof', 'Fresh session did not recover watchlist')
assert(accounts.length === 1 && accounts[0].status === 'follow-up' && accounts[0].note === 'cross-session proof', 'Fresh session did not recover account workflow state')
assert(memberships.length === 1 && memberships[0].watchlist_id === watchlistId, 'Fresh session did not recover watchlist membership')

const isolated = await signUp(otherEmail)
const isolatedWatchlists = await dataRequest(isolated.jwt, `workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}&select=watchlist_id`)
const isolatedAccounts = await dataRequest(isolated.jwt, `workflow_accounts?system_id=eq.${encodeURIComponent(systemId)}&select=system_id`)
assert(isolatedWatchlists.length === 0, 'RLS isolation failed: second user can read first user watchlist')
assert(isolatedAccounts.length === 0, 'RLS isolation failed: second user can read first user account state')

await dataRequest(secondSession.jwt, `workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}`, { method: 'DELETE' })
const membershipsAfterWatchlistDelete = await dataRequest(secondSession.jwt, `workflow_watchlist_members?system_id=eq.${encodeURIComponent(systemId)}&select=watchlist_id,system_id`)
assert(membershipsAfterWatchlistDelete.length === 0, 'Cascade cleanup did not remove watchlist membership')
await dataRequest(secondSession.jwt, `workflow_accounts?system_id=eq.${encodeURIComponent(systemId)}`, { method: 'DELETE' })
const accountAfterCleanup = await dataRequest(secondSession.jwt, `workflow_accounts?system_id=eq.${encodeURIComponent(systemId)}&select=system_id`)
assert(accountAfterCleanup.length === 0, 'Explicit account cleanup failed')

console.log(JSON.stringify({
  result: 'PASS',
  cross_session_recovery: true,
  rls_user_isolation: true,
  membership_cascade_cleanup: true,
  account_cleanup: true,
  test_system_id: systemId,
}))
