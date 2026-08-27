import { webkit } from '@playwright/test'

const baseUrl = 'https://jeremyhennessy.github.io/TowerSignal/'
const authBase = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const runId = process.env.GITHUB_RUN_ID || Date.now().toString()
const email = `towersignal-webkit-cookie-${runId}@example.com`
const password = 'TowerSignal-Diagnostic-2026!'

const browser = await webkit.launch()
const page = await browser.newPage()
await page.goto(baseUrl, { waitUntil: 'networkidle' })

const result = await page.evaluate(async ({ authBase, email, password }) => {
  const headers = { 'content-type': 'application/json', 'x-neon-client-info': JSON.stringify({ sdk:'diagnostic', version:'1', runtime:'browser' }) }
  const signup = await fetch(`${authBase}/sign-up/email`, {
    method: 'POST', credentials: 'include', headers,
    body: JSON.stringify({ email, password, name: 'WebKit Cookie Diagnostic' }),
  })
  const signupBody = await signup.json()
  const immediate = await fetch(`${authBase}/get-session`, { method: 'GET', credentials: 'include', headers: { 'x-neon-client-info': headers['x-neon-client-info'] } })
  const immediateBody = await immediate.json()
  return {
    signupStatus: signup.status,
    signupTokenPresent: typeof signupBody?.token === 'string',
    immediateStatus: immediate.status,
    immediateAuthenticated: Boolean(immediateBody?.session && immediateBody?.user),
    immediateSessionKeys: immediateBody?.session ? Object.keys(immediateBody.session) : [],
    immediateJwtLike: typeof immediateBody?.session?.token === 'string' && immediateBody.session.token.split('.').length === 3,
    immediateSetAuthJwtPresent: Boolean(immediate.headers.get('set-auth-jwt')),
  }
}, { authBase, email, password })

console.log(JSON.stringify(result, null, 2))
await browser.close()
if (!result.immediateAuthenticated) process.exit(2)
