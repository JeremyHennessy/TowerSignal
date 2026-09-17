const BRIDGE_URL = 'https://br-small-resonance-auw6h71b-authbridgeproof.compute.c-10.us-east-1.aws.neon.tech'
const DATA_API_URL = 'https://ep-nameless-brook-auxfp8jj.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'
const ORIGIN = 'https://jeremyhennessy.github.io'
const runId = process.env.GITHUB_RUN_ID || Date.now().toString()
const email = `towersignal-sealed-bridge-${runId}@example.com`
const password = 'TowerSignal-E2E-2026!'
const watchlistId = `sealed-bridge-${runId}`

function assert(condition, message) {
  if (!condition) throw new Error(message)
}
async function body(response) {
  const text = await response.text()
  try { return text ? JSON.parse(text) : null } catch { return { raw: text.slice(0, 200) } }
}
async function bridge(path, payload, refresh, origin = ORIGIN) {
  const response = await fetch(`${BRIDGE_URL}${path}`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      origin,
      ...(refresh ? { authorization: `Bearer ${refresh}` } : {}),
    },
    body: payload === undefined ? '{}' : JSON.stringify(payload),
  })
  return { response, payload: await body(response.clone()) }
}

const signup = await bridge('/sign-up', { email, password, name: 'Sealed Bridge Proof' })
assert(signup.response.ok, `bridge sign-up failed ${signup.response.status}: ${JSON.stringify(signup.payload)}`)
assert(typeof signup.payload?.token === 'string' && signup.payload.token.split('.').length === 3, 'sign-up did not return JWT')
assert(typeof signup.payload?.refresh === 'string' && signup.payload.refresh.length > 80, 'sign-up did not return sealed refresh credential')
assert(signup.payload?.user?.email === email, 'sign-up user identity mismatch')
assert(signup.response.headers.get('cache-control') === 'no-store', 'bridge sign-up must be no-store')
assert(signup.response.headers.get('access-control-allow-origin') === ORIGIN, 'bridge sign-up CORS origin mismatch')

const auth = token => ({ authorization: `Bearer ${token}`, 'content-type': 'application/json' })
const insert = await fetch(`${DATA_API_URL}/workflow_watchlists`, {
  method: 'POST',
  headers: { ...auth(signup.payload.token), prefer: 'return=representation' },
  body: JSON.stringify({ watchlist_id: watchlistId, name: 'Sealed bridge proof' }),
})
const insertBody = await body(insert.clone())
assert(insert.ok, `RLS insert failed ${insert.status}: ${JSON.stringify(insertBody)}`)
assert(Array.isArray(insertBody) && insertBody.some(row => row.watchlist_id === watchlistId), 'RLS insert missing proof row')

const refresh = await bridge('/session', undefined, signup.payload.refresh)
assert(refresh.response.ok, `bridge session refresh failed ${refresh.response.status}: ${JSON.stringify(refresh.payload)}`)
assert(refresh.payload?.user?.email === email, 'refreshed user identity mismatch')
assert(typeof refresh.payload?.token === 'string' && refresh.payload.token.split('.').length === 3, 'session refresh did not return JWT')
assert(typeof refresh.payload?.refresh === 'string' && refresh.payload.refresh.length > 80, 'session refresh did not return sealed refresh')

const select = await fetch(`${DATA_API_URL}/workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}&select=watchlist_id,name`, {
  headers: auth(refresh.payload.token),
})
const selectBody = await body(select.clone())
assert(select.ok, `RLS select failed ${select.status}: ${JSON.stringify(selectBody)}`)
assert(Array.isArray(selectBody) && selectBody.length === 1 && selectBody[0].watchlist_id === watchlistId, 'RLS select missing proof row')

const remove = await fetch(`${DATA_API_URL}/workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}`, {
  method: 'DELETE',
  headers: auth(refresh.payload.token),
})
assert(remove.ok, `RLS cleanup failed ${remove.status}: ${await remove.text()}`)

const wrongOrigin = await bridge('/session', undefined, refresh.payload.refresh, 'https://example.com')
assert(wrongOrigin.response.status === 403, `wrong origin must be 403, got ${wrongOrigin.response.status}`)

const signout = await bridge('/sign-out', undefined, refresh.payload.refresh)
assert(signout.response.ok, `bridge sign-out failed ${signout.response.status}: ${JSON.stringify(signout.payload)}`)
const afterSignout = await bridge('/session', undefined, refresh.payload.refresh)
assert(afterSignout.response.status === 401, `session must be invalid after sign-out, got ${afterSignout.response.status}`)

console.log(JSON.stringify({
  signup_status: signup.response.status,
  jwt_shape: signup.payload.token.split('.').length,
  sealed_refresh_length: signup.payload.refresh.length,
  rls_insert_status: insert.status,
  refresh_status: refresh.response.status,
  rls_select_status: select.status,
  rls_cleanup_status: remove.status,
  wrong_origin_status: wrongOrigin.response.status,
  signout_status: signout.response.status,
  after_signout_status: afterSignout.response.status,
  result: 'SEALED_SESSION_BRIDGE_RLS_PROOF_OK',
}, null, 2))
