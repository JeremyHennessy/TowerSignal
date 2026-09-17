const AUTH_URL = process.env.BRIDGE_PROOF_AUTH_URL
const BRIDGE_URL = process.env.BRIDGE_PROOF_URL
const DATA_API_URL = process.env.BRIDGE_PROOF_DATA_API_URL
const ORIGIN = 'https://jeremyhennessy.github.io'
const runId = process.env.GITHUB_RUN_ID || Date.now().toString()
const email = `towersignal-auth-bridge-${runId}@example.com`
const password = 'TowerSignal-E2E-2026!'
const watchlistId = `bridge-proof-${runId}`

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

async function readJson(response) {
  const text = await response.text()
  try { return text ? JSON.parse(text) : null } catch { return { raw: text.slice(0, 200) } }
}

assert(AUTH_URL && BRIDGE_URL && DATA_API_URL, 'Bridge proof environment is incomplete')

const signUp = await fetch(`${AUTH_URL}/sign-up/email`, {
  method: 'POST',
  headers: { 'content-type': 'application/json', origin: ORIGIN },
  body: JSON.stringify({ email, password, name: 'Auth Bridge Proof' }),
})
const signUpBody = await readJson(signUp.clone())
assert(signUp.ok, `sign-up failed ${signUp.status}: ${JSON.stringify(signUpBody)}`)
assert(typeof signUpBody?.token === 'string' && signUpBody.token.length > 20, 'sign-up did not return an opaque session token')

const bridge = await fetch(BRIDGE_URL, {
  method: 'POST',
  headers: { 'content-type': 'application/json', origin: ORIGIN },
  body: JSON.stringify({ sessionToken: signUpBody.token }),
})
const bridgeBody = await readJson(bridge.clone())
assert(bridge.ok, `bridge failed ${bridge.status}: ${JSON.stringify(bridgeBody)}`)
assert(typeof bridgeBody?.token === 'string' && bridgeBody.token.split('.').length === 3, 'bridge did not return a JWT-shaped token')

const authHeaders = {
  authorization: `Bearer ${bridgeBody.token}`,
  'content-type': 'application/json',
}

const insert = await fetch(`${DATA_API_URL}/workflow_watchlists`, {
  method: 'POST',
  headers: { ...authHeaders, prefer: 'return=representation' },
  body: JSON.stringify({ watchlist_id: watchlistId, name: 'Auth bridge proof' }),
})
const insertBody = await readJson(insert.clone())
assert(insert.ok, `Data API insert failed ${insert.status}: ${JSON.stringify(insertBody)}`)
assert(Array.isArray(insertBody) && insertBody.some(row => row.watchlist_id === watchlistId), 'RLS insert did not return proof watchlist')

const select = await fetch(`${DATA_API_URL}/workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}&select=watchlist_id,name`, { headers: authHeaders })
const selectBody = await readJson(select.clone())
assert(select.ok, `Data API select failed ${select.status}: ${JSON.stringify(selectBody)}`)
assert(Array.isArray(selectBody) && selectBody.length === 1 && selectBody[0].watchlist_id === watchlistId, 'RLS select did not return proof watchlist')

const remove = await fetch(`${DATA_API_URL}/workflow_watchlists?watchlist_id=eq.${encodeURIComponent(watchlistId)}`, {
  method: 'DELETE',
  headers: authHeaders,
})
assert(remove.ok, `Data API cleanup failed ${remove.status}: ${await remove.text()}`)

const wrongOrigin = await fetch(BRIDGE_URL, {
  method: 'POST',
  headers: { 'content-type': 'application/json', origin: 'https://example.com' },
  body: JSON.stringify({ sessionToken: signUpBody.token }),
})
assert(wrongOrigin.status === 403, `bridge must reject untrusted origins; got ${wrongOrigin.status}`)

console.log(JSON.stringify({
  signup_status: signUp.status,
  bridge_status: bridge.status,
  jwt_shape: bridgeBody.token.split('.').length,
  data_api_insert_status: insert.status,
  data_api_select_status: select.status,
  data_api_cleanup_status: remove.status,
  wrong_origin_status: wrongOrigin.status,
  result: 'AUTH_BRIDGE_RLS_PROOF_OK',
}, null, 2))
