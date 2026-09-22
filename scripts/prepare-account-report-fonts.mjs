// Pinned upstream Inter webfonts, isolated to the approved Account PDF.
// Build fails rather than shipping a silently substituted report typeface.
import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
const commit = 'e3a3d4c57d5ecc01453a575621882a384c1995a3'
const base = `https://raw.githubusercontent.com/rsms/inter/${commit}/`
const directory = new URL('../public/report-assets/', import.meta.url)
await mkdir(directory, { recursive: true })
const weights = ['Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold']
const manifest = { upstream: 'rsms/inter', commit, files: {} }
for (const file of [...weights.map(w => `Inter-${w}.woff2`), 'LICENSE.txt']) {
  const path = file === 'LICENSE.txt' ? 'LICENSE.txt' : `docs/font-files/${file}`
  const target = new URL(file, directory)
  let bytes
  try { bytes = await readFile(target) } catch { /* Fetch only absent build assets. */ }
  if (!bytes) {
    const response = await fetch(base + path, { signal: AbortSignal.timeout(30000) })
    if (!response.ok) throw new Error(`Report font ${file}: HTTP ${response.status}`)
    bytes = Buffer.from(await response.arrayBuffer())
  }
  if (file.endsWith('.woff2') && (bytes.subarray(0, 4).toString() !== 'wOF2' || bytes.length < 10000)) throw new Error(`Invalid report webfont: ${file}`)
  await writeFile(target, bytes)
  manifest.files[file] = createHash('sha256').update(bytes).digest('hex')
}
await writeFile(new URL('manifest.json', directory), JSON.stringify(manifest, null, 2) + '\n')
console.log('Prepared pinned Inter Account PDF assets')
