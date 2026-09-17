const AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const ORIGIN = 'https://jeremyhennessy.github.io'
const email = `towersignal-jwt-lifetime-${process.env.GITHUB_RUN_ID || Date.now()}@example.com`
const password = 'TowerSignal-E2E-2026!'

function cookieHeader(response) {
  const values = typeof response.headers.getSetCookie === 'function'
    ? response.headers.getSetCookie()
    : [response.headers.get('set-cookie')].filter(Boolean)
  return values.map(value => value.split(';', 1)[0]).join('; ')
}
function decodeJwt(token) {
  const part = token.split('.')[1]
  const normalized = part.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - part.length % 4) % 4)
  return JSON.parse(Buffer.from(normalized, 'base64').toString('utf8'))
}
const signup = await fetch(`${AUTH_URL}/sign-up/email`, {
  method: 'POST',
  headers: { 'content-type': 'application/json', origin: ORIGIN },
  body: JSON.stringify({ email, password, name: 'JWT Lifetime Probe' }),
})
if (!signup.ok) throw new Error(`sign-up failed ${signup.status}`)
const cookie = cookieHeader(signup)
if (!cookie) throw new Error('sign-up returned no session cookie')
const tokenResponse = await fetch(`${AUTH_URL}/token`, { headers: { cookie, origin: ORIGIN } })
if (!tokenResponse.ok) throw new Error(`/token failed ${tokenResponse.status}`)
const body = await tokenResponse.json()
if (typeof body.token !== 'string' || body.token.split('.').length !== 3) throw new Error('/token did not return JWT')
const payload = decodeJwt(body.token)
const lifetime = Number(payload.exp || 0) - Number(payload.iat || 0)
console.log(JSON.stringify({
  token_status: tokenResponse.status,
  jwt_lifetime_seconds: lifetime,
  jwt_lifetime_minutes: Math.round(lifetime / 60 * 100) / 100,
  has_sub: Boolean(payload.sub),
  role: payload.role || null,
}, null, 2))
