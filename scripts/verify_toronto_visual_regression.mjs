import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import { mkdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

const [baselineDist, candidateDist, outputDir = 'artifacts/toronto-visual-regression'] = process.argv.slice(2)
if (!baselineDist || !candidateDist) {
  throw new Error('Usage: node scripts/verify_toronto_visual_regression.mjs <baseline-dist> <candidate-dist> [output-dir]')
}

await mkdir(outputDir, { recursive: true })

function serve(directory, port) {
  const child = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1', '--directory', directory], {
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  child.stderr.on('data', chunk => process.stderr.write(chunk))
  return child
}

async function waitForServer(url) {
  let lastError
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch (error) {
      lastError = error
    }
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw lastError ?? new Error(`Server did not become reachable: ${url}`)
}

const baselinePort = 41731
const candidatePort = 41732
const baselineServer = serve(baselineDist, baselinePort)
const candidateServer = serve(candidateDist, candidatePort)
const baselineOrigin = `http://127.0.0.1:${baselinePort}`
const candidateOrigin = `http://127.0.0.1:${candidatePort}`

try {
  await Promise.all([waitForServer(baselineOrigin), waitForServer(candidateOrigin)])
  const browser = await chromium.launch({ headless: true })
  try {
    const cases = [
      { name: 'desktop', viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 },
      { name: 'iphone', viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 },
    ]
    const entries = [
      { name: 'toronto', hash: '#/toronto' },
      { name: 'prospect-entry', hash: '#/prospect' },
    ]

    for (const testCase of cases) {
      for (const entry of entries) {
        const screenshots = []
        for (const target of [
          { label: 'approved-equivalent', origin: baselineOrigin },
          { label: 'candidate', origin: candidateOrigin },
        ]) {
          const context = await browser.newContext({
            viewport: testCase.viewport,
            deviceScaleFactor: testCase.deviceScaleFactor,
          })
          await context.route('**/*', route => {
            const url = new URL(route.request().url())
            if (url.hostname === '127.0.0.1' || url.hostname === 'localhost') {
              return route.continue()
            }
            return route.abort()
          })
          const page = await context.newPage()
          await page.goto(`${target.origin}/${entry.hash}`, { waitUntil: 'networkidle' })
          await page.locator('h1').filter({ hasText: 'Toronto Market' }).waitFor({ state: 'visible' })
          await page.addStyleTag({
            content: `*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }`,
          })
          await page.waitForTimeout(250)
          const path = join(outputDir, `${entry.name}-${testCase.name}-${target.label}.png`)
          await page.screenshot({ path, fullPage: false })
          screenshots.push(path)
          await context.close()
        }

        const [baseline, candidate] = await Promise.all(screenshots.map(path => readFile(path)))
        if (!baseline.equals(candidate)) {
          throw new Error(`Visual regression detected for ${entry.name}/${testCase.name}: screenshots are not pixel-identical`)
        }
        console.log(`VISUAL_MATCH ${entry.name}/${testCase.name}`)
      }
    }
  } finally {
    await browser.close()
  }
} finally {
  baselineServer.kill('SIGTERM')
  candidateServer.kill('SIGTERM')
}
