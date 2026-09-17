const AUTH_URL = process.env.TOWERSIGNAL_WORKFLOW_AUTH_URL || 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const ORIGIN = process.env.TOWERSIGNAL_ORIGIN || 'https://jeremyhennessy.github.io'
const runId = process.env.GITHUB_RUN_ID || Date.now().toString()
const attempt = process.env.GITHUB_RUN_ATTEMPT || '1'
const email = `towersignal-bearer-probe-${runId}-${attempt}@example.com`
const password = 'TowerSignal-E2E-2026!'

function cookieHeader(response) {
  const values = typeof response.headers.getSetCookie === 'function'
    ? response.headers.getSetCookie()
    : [response.headers.get('set-cookie')].filter(Boolean)
  return values.map(value => value.split(';', 1)[0]).join('; ')
}

async function json(response) {
  const text = await response.text()
  try { return text ? JSON.parse(text) : null } catch { return { rawLength: text.length } }
}

const signUp = await fetch(`${AUTH_URL}/sign-up/email`, {
  method: 'POST',
  headers: { 'content-type': 'application/json', origin: ORIGIN },
  body: JSON.stringify({ email, password, name: 'Bearer Probe' }),
})
const signUpBody = await json(signUp.clone())
if (!signUp.ok) throw new Error(`sign-up failed ${signUp.status}: ${JSON.stringify(signUpBody)}`)
const opaqueToken = signUpBody?.token
if (!opaqueToken || typeof opaqueToken !== 'string') throw new Error(`sign-up did not return opaque session token; keys=${Object.keys(signUpBody || {}).join(',')}`)

const cookie = cookieHeader(signUp)
const cookieTokenResponse = await fetch(`${AUTH_URL}/token`, {
  headers: { cookie, origin: ORIGIN },
})
const cookieTokenBody = await json(cookieTokenResponse.clone())

const bearerTokenResponse = await fetch(`${AUTH_URL}/token`, {
  headers: { authorization: `Bearer ${opaqueToken}`, origin: ORIGIN },
})
const bearerTokenBody = await json(bearerTokenResponse.clone())

const bearerSessionResponse = await fetch(`${AUTH_URL}/get-session`, {
  headers: { authorization: `Bearer ${opaqueToken}`, origin: ORIGIN },
})
const bearerSessionBody = await json(bearerSessionResponse.clone())

const result = {
  signup_status: signUp.status,
  signup_keys: Object.keys(signUpBody || {}),
  signup_has_cookie: Boolean(cookie),
  cookie_token_status: cookieTokenResponse.status,
  cookie_token_keys: Object.keys(cookieTokenBody || {}),
  cookie_token_has_jwt_header: Boolean(cookieTokenResponse.headers.get('set-auth-jwt')),
  bearer_token_status: bearerTokenResponse.status,
  bearer_token_keys: Object.keys(bearerTokenBody || {}),
  bearer_token_has_jwt_header: Boolean(bearerTokenResponse.headers.get('set-auth-jwt')),
  bearer_session_status: bearerSessionResponse.status,
  bearer_session_has_user: Boolean(bearerSessionBody?.user),
  bearer_session_has_session: Boolean(bearerSessionBody?.session),
  bearer_session_has_jwt_header: Boolean(bearerSessionResponse.headers.get('set-auth-jwt')),
}
console.log(JSON.stringify(result, null, 2))

if (bearerTokenResponse.ok && (bearerTokenBody?.token || bearerTokenResponse.headers.get('set-auth-jwt'))) {
  console.log('BEARER_SESSION_EXCHANGE=SUPPORTED')
} else {
  console.log('BEARER_SESSION_EXCHANGE=UNSUPPORTED')
}
