// Pinned upstream assets, used only by the approved Account PDF.
import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
const commit = 'e3a3d4c57d5ecc01453a575621882a384c1995a3'
const base = `https://raw.githubusercontent.com/rsms/inter/${commit}/`
const directory = new URL('../public/report-assets/', import.meta.url)
const expected = {
  'Inter-Regular.woff2': 'e06f6b1bc553aaea4e4668023ed0ab0a147129c3107f511bc7d03d361b0ae085',
  'Inter-Medium.woff2': '0ff3e94614e1493eb556314fd247ae6c4a85a7783b4cc86be539940cf83f2a48',
  'Inter-SemiBold.woff2': '5cb7103e4e605989afebc03d989c79201e54b21b5183db33981f70db9178a301',
  'Inter-Bold.woff2': 'fa888127b6da015b65569f0351f3b5c391ad928904951f1c20e9f8462a8d95ea',
  'Inter-ExtraBold.woff2': '6f75025856f8db1b2186e9cb89be9de9894932c8b7b20f4df5e65916ff714e34',
  'LICENSE.txt': '262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a',
}
await mkdir(directory, { recursive: true })
for (const [file, digest] of Object.entries(expected)) {
  const target = new URL(file, directory)
  let bytes
  try { bytes = await readFile(target) } catch { /* Only absent assets are fetched. */ }
  if (!bytes) {
    const response = await fetch(base + (file === 'LICENSE.txt' ? file : `docs/font-files/${file}`), { signal: AbortSignal.timeout(30000) })
    if (!response.ok) throw new Error(`Report asset ${file}: HTTP ${response.status}`)
    bytes = Buffer.from(await response.arrayBuffer())
  }
  if (createHash('sha256').update(bytes).digest('hex') !== digest) throw new Error(`Report asset integrity mismatch: ${file}`)
  await writeFile(target, bytes)
}
await writeFile(new URL('manifest.json', directory), JSON.stringify({ upstream: 'rsms/inter', commit, files: expected }, null, 2) + '\n')
console.log('Verified pinned Inter Account PDF assets')
