const UPSTREAM_AUTH_ORIGIN = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech'
const UPSTREAM_AUTH_BASE = '/neondb/auth'
const EXISTING_TRUSTED_ORIGIN = 'https://jeremyhennessy.github.io'

function rewriteSetCookie(cookie) {
  return cookie
    .replace(/;\s*Domain=[^;]+/gi, '')
    .replace(/;\s*Partitioned/gi, '')
}

export async function onRequest(context) {
  const incoming = new URL(context.request.url)
  const requestOrigin = context.request.headers.get('Origin')

  if (requestOrigin && requestOrigin !== incoming.origin) {
    return new Response('Cross-origin auth proxy requests are not allowed.', { status: 403 })
  }

  const suffix = incoming.pathname.slice('/api/auth'.length)
  const upstream = new URL(`${UPSTREAM_AUTH_ORIGIN}${UPSTREAM_AUTH_BASE}${suffix}${incoming.search}`)
  const headers = new Headers(context.request.headers)

  headers.delete('Host')
  headers.delete('Referer')
  if (requestOrigin) headers.set('Origin', EXISTING_TRUSTED_ORIGIN)

  const body = ['GET', 'HEAD'].includes(context.request.method) ? undefined : context.request.body
  const upstreamResponse = await fetch(upstream, {
    method: context.request.method,
    headers,
    body,
    redirect: 'manual',
  })

  const responseHeaders = new Headers(upstreamResponse.headers)
  const getSetCookie = upstreamResponse.headers.getSetCookie?.bind(upstreamResponse.headers)
  const cookies = getSetCookie ? getSetCookie() : []

  responseHeaders.delete('Access-Control-Allow-Origin')
  responseHeaders.delete('Access-Control-Allow-Credentials')
  responseHeaders.delete('Set-Cookie')
  for (const cookie of cookies) responseHeaders.append('Set-Cookie', rewriteSetCookie(cookie))

  const location = responseHeaders.get('Location')
  if (location?.startsWith(`${UPSTREAM_AUTH_ORIGIN}${UPSTREAM_AUTH_BASE}`)) {
    responseHeaders.set('Location', location.replace(`${UPSTREAM_AUTH_ORIGIN}${UPSTREAM_AUTH_BASE}`, `${incoming.origin}/api/auth`))
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  })
}
