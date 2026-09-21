import type { Page } from '@playwright/test'
import { gzipSync } from 'node:zlib'
import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'

const installed = new WeakSet<Page>()
const maxInlineBytes = 32 * 1024 * 1024
const contentTypes: Record<string, string> = {
  '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.jpg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2',
}

// Opt-in predeployment proof only. Hosted acceptance never sets CANDIDATE_ROOT.
// Inline the candidate application and frozen data. Oversized retained JSON is
// gzip-compressed for route transport so the browser receives the exact decompressed
// candidate bytes without consulting current hosted data or changing authentication.
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
        if (!relative.startsWith('data/')) throw new Error('Oversized non-data candidate asset cannot use frozen transport')
        const compressed = gzipSync(await readFile(target), { level: 6 })
        if (compressed.length > 96 * 1024 * 1024) throw new Error('Compressed frozen candidate source exceeds safe route transport bound')
        await route.fulfill({
          status: 200,
          contentType: contentTypes[path.extname(target)] ?? 'application/octet-stream',
          headers: { 'content-encoding': 'gzip' },
          body: compressed,
        })
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
