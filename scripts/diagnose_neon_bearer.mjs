const authBase = process.env.NEON_AUTH_BASE_URL || 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const origin = 'https://jeremyhennessy.github.io'
const runId = process.env.GITHUB_RUN_ID || Date.now().toString()
const email = `towersignal-bearer-diagnostic-${runId}@example.com`
const password = 'TowerSignal-Diagnostic-2026!'

async function request(path, init = {}) {
  const response = await fetch(`${authBase}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      origin,
      ...(init.headers || {}),
    },
  })
  const text = await response.text()
  let body = null
  try { body = text ? JSON.parse(text) : null } catch { body = text }
  return { response, body }
}

const signup = await request('/sign-up/email', {
  method: 'POST',
  body: JSON.stringify({ email, password, name: 'Bearer Diagnostic' }),
})

if (!signup.response.ok) {
  console.error(JSON.stringify({ stage: 'signup', status: signup.response.status, body: signup.body }, null, 2))
  process.exit(1)
}

const bodyToken = typeof signup.body?.token === 'string' ? signup.body.token : null
const headerToken = signup.response.headers.get('set-auth-token')
const setCookie = signup.response.headers.get('set-cookie')
const cookieValue = setCookie?.match(/__Secure-better-auth\.session_token=([^;]+)/)?.[1] || null

const candidates = [
  ['body_token', bodyToken],
  ['set_auth_token_header', headerToken],
  ['cookie_token_value', cookieValue],
].filter(([, token]) => typeof token === 'string' && token.length > 0)

const results = []
for (const [label, token] of candidates) {
  const session = await request('/get-session', {
    method: 'GET',
    headers: { authorization: `Bearer ${token}` },
  })
  results.push({
    candidate: label,
    status: session.response.status,
    authenticated: Boolean(session.body?.session && session.body?.user),
    body_shape: session.body && typeof session.body === 'object' ? Object.keys(session.body) : typeof session.body,
  })
}

console.log(JSON.stringify({
  signup_status: signup.response.status,
  body_token_present: Boolean(bodyToken),
  set_auth_token_header_present: Boolean(headerToken),
  session_cookie_present: Boolean(cookieValue),
  results,
}, null, 2))

if (!results.some(result => result.authenticated)) process.exit(2)
