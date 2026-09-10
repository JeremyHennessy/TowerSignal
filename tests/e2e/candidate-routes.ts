import type { Page } from '@playwright/test'
import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'

const installed = new WeakSet<Page>()
const verifiedSources = new Map<string, Promise<void>>()
const maxInlineBytes = 32 * 1024 * 1024
const contentTypes: Record<string, string> = {
  '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.jpg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2',
}

async function verifyHostedSource(target: string, url: string): Promise<void> {
  const expected = createHash('sha256')
  for await (const chunk of createReadStream(target)) expected.update(chunk)
  const digest = expected.digest('hex')
  const key = `${url}:${digest}`
  let verification = verifiedSources.get(key)
  if (!verification) {
    verification = (async () => {
      const response = await fetch(url, { cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(90_000) })
      if (!response.ok || !response.body) throw new Error(`Retained source HTTP ${response.status}: ${url}`)
      const actual = createHash('sha256')
      for await (const chunk of response.body) actual.update(chunk)
      if (actual.digest('hex') !== digest) throw new Error(`Hosted source differs from exact candidate artifact: ${url}`)
      console.info(`[candidate transport] Verified retained source SHA-256 ${digest}: ${url}`)
    })()
    verifiedSources.set(key, verification)
  }
  await verification
}

// Opt-in predeployment proof only. Hosted acceptance never sets CANDIDATE_ROOT.
// Inline the candidate application and new data. Oversized retained sources use
// normal HTTPS only after their hosted bytes match the exact artifact SHA-256.
// This avoids Chromium's 100 MiB DevTools input limit without truncating data,
// mocking records, changing authentication, or substituting unverified sources.
export async function installCandidateRoutes(page: Page): Promise<void> {
  const candidateRoot = process.env.CANDIDATE_ROOT
  if (!candidateRoot || installed.has(page)) return
  const root = path.resolve(candidateRoot)
  const base = 'https://jeremyhennessy.github.io/TowerSignal/'
  await page.route(`${base}**`, async route => {
    const url = new URL(route.request().url())
    const relative = decodeURIComponent(url.pathname.slice('/TowerSignal/'.length)) || 'index.html'
    const target = path.resolve(root, relative)
    if (!target.startsWith(root + path.sep)) throw new Error('Candidate path escaped artifact root')
    try {
      if ((await stat(target)).size > maxInlineBytes) {
        if (!relative.startsWith('data/')) throw new Error('Oversized non-data candidate asset cannot use retained-source transport')
        await verifyHostedSource(target, url.href)
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: contentTypes[path.extname(target)] ?? 'application/octet-stream', body: await readFile(target) })
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
      await route.fulfill({ status: 404, body: 'Not present in candidate artifact' })
    }
  })
  installed.add(page)
}
