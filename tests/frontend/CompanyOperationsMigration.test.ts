import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const sql = readFileSync('database/migrations/004_company_operations.sql', 'utf8')

test('company operations migration adds private queue and field-level audit', () => {
  expect(sql).toContain('CREATE TABLE IF NOT EXISTS public.company_private_research_queue')
  expect(sql).toContain('CREATE TABLE IF NOT EXISTS public.company_private_change_log')
  expect(sql).toContain('towersignal_audit_company_change')
  expect(sql).toContain('company_private_profiles_audit')
  expect(sql).toContain('company_private_contacts_audit')
  expect(sql).toContain('company_private_activities_audit')
  expect(sql).toContain('company_private_notes_audit')
  expect(sql).toContain('company_private_research_audit')
  expect(sql).toContain('ALTER TABLE public.company_private_research_queue ENABLE ROW LEVEL SECURITY')
  expect(sql).toContain('ALTER TABLE public.company_private_change_log ENABLE ROW LEVEL SECURITY')
  expect(sql).toContain('USING (public.towersignal_is_admin())')
  expect(sql).not.toContain('DISABLE ROW LEVEL SECURITY')
})
