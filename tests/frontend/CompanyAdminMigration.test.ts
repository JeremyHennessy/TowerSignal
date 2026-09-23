import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const sql = readFileSync('database/migrations/002_company_database.sql', 'utf8')

test('company database migration enforces admin-only RLS for every private table', () => {
  expect(sql).toContain('neon_auth."user"')
  expect(sql).toContain("lower(coalesce(u.role, '')) = 'admin'")
  expect(sql).toContain('CREATE OR REPLACE VIEW public.company_admin_access')
  for (const table of [
    'company_private_profiles',
    'company_private_contacts',
    'company_private_activities',
    'company_private_notes',
  ]) {
    expect(sql).toContain(`ALTER TABLE public.${table} ENABLE ROW LEVEL SECURITY`)
    expect(sql).toContain(`ON public.${table}`)
  }
  expect((sql.match(/USING \(public\.towersignal_is_admin\(\)\)/g) ?? []).length).toBe(4)
  expect((sql.match(/WITH CHECK \(public\.towersignal_is_admin\(\)\)/g) ?? []).length).toBe(4)
})
