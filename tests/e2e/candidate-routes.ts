import type { Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

const installed = new WeakSet<Page>()
const contentTypes: Record<string, string> = {
  '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.jpg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2',
}

// Opt-in predeployment proof only. Hosted acceptance never sets CANDIDATE_ROOT.
// All first-party responses come from the exact built artifact; authentication
// and map services remain real third-party requests.
export async function installCandidateRoutes(page: Page): Promise<void> {
  const candidateRoot = process.env.CANDIDATE_ROOT
  if (!candidateRoot || installed.has(page)) return
  const root = path.resolve(candidateRoot)
  const base = 'https://jeremyhennessy.github.io/TowerSignal/'
  await page.route(`${base}**`, async route => {
    const relative = decodeURIComponent(new URL(route.request().url()).pathname.slice('/TowerSignal/'.length)) || 'index.html'
    const target = path.resolve(root, relative)
    if (!target.startsWith(root + path.sep)) throw new Error('Candidate path escaped artifact root')
    try {
      await route.fulfill({ status: 200, contentType: contentTypes[path.extname(target)] ?? 'application/octet-stream', body: await readFile(target) })
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
      await route.fulfill({ status: 404, body: 'Not present in candidate artifact' })
    }
  })
  installed.add(page)
}
