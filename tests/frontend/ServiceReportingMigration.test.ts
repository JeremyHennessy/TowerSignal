import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const sql = readFileSync('database/migrations/005_service_reporting_foundation.sql', 'utf8')

test('service reporting migration creates normalized admin-only operational model', () => {
  for (const table of [
    'service_clients',
    'service_portfolios',
    'service_sites',
    'service_assets',
    'service_agreements',
    'service_visits',
    'service_measurements',
    'service_actions',
    'service_reports',
    'service_documents',
    'service_change_log',
  ]) {
    expect(sql).toContain(`public.${table}`)
  }
  expect(sql).toContain('system_id text NOT NULL UNIQUE')
  expect(sql).toContain('extraction_status')
  expect(sql).toContain('extracted_text')
  expect(sql).toContain('towersignal_audit_service_change')
  expect(sql).toContain('ENABLE ROW LEVEL SECURITY')
  expect(sql).toContain('towersignal_is_admin()')
  expect(sql).not.toContain('DISABLE ROW LEVEL SECURITY')
})

const refinement = readFileSync('database/migrations/004a_company_audit_refinement.sql', 'utf8')

test('repository records the applied concise company-audit refinement', () => {
  expect(refinement).toContain("TG_OP = 'INSERT'")
  expect(refinement).toContain("new_value = 'null'::jsonb")
  expect(refinement).toContain('company_private_change_log')
})
