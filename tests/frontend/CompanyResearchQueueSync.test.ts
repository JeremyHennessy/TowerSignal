import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const source = readFileSync('src/companyAdmin/client.ts', 'utf8')

test('research queue sync preserves workflow state and removes stale rows', () => {
  expect(source).toContain("const current = await loadCompanyResearchQueue()")
  expect(source).toContain("status: existing?.status ?? 'unreviewed'")
  expect(source).toContain("research_owner: existing?.research_owner ?? null")
  expect(source).toContain("last_researched_at: existing?.last_researched_at ?? null")
  expect(source).toContain("const stale = current.filter(item => !desiredIds.has(item.company_id))")
  expect(source).toContain("deleteCompanyResearchQueueItem")
  expect(source).toContain("candidates.length !== 100")
})
