import { createClient } from '@neondatabase/neon-js'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminNote,
  CompanyAdminProfile,
  CompanyAdminProfilePatch,
  CompanyAdminSnapshot,
  CompanyAuditEntry,
  CompanyResearchQueueItem,
  CompanyResearchStatus,
} from '../types/companyAdmin'

const DEFAULT_AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const DEFAULT_DATA_API_URL = 'https://ep-silent-moon-au2icaki.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'

const client = createClient({
  auth: { url: import.meta.env.VITE_NEON_AUTH_URL || DEFAULT_AUTH_URL },
  dataApi: { url: import.meta.env.VITE_NEON_DATA_API_URL || DEFAULT_DATA_API_URL },
})

export const companyAdminRuntimeEnabled = import.meta.env.MODE !== 'test'

function message(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error) return String((error as { message?: unknown }).message ?? 'Unknown company database error')
  return String(error || 'Unknown company database error')
}

function throwIfError(context: string, error: unknown): void {
  if (error) throw new Error(`${context}: ${message(error)}`)
}

function nullableString(value: unknown): string | null {
  if (value == null) return null
  const text = String(value).trim()
  return text || null
}

function nullableNumber(value: unknown): number | null {
  if (value == null || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function profileFrom(row: Record<string, unknown>): CompanyAdminProfile {
  return {
    company_id: String(row.company_id),
    canonical_name: String(row.canonical_name ?? ''),
    legal_name: nullableString(row.legal_name),
    rollup_name: nullableString(row.rollup_name),
    rollup_company_id: nullableString(row.rollup_company_id),
    rollup_source_name: nullableString(row.rollup_source_name),
    rollup_source_url: nullableString(row.rollup_source_url),
    website: nullableString(row.website),
    website_source_name: nullableString(row.website_source_name),
    website_source_url: nullableString(row.website_source_url),
    identity_source_name: nullableString(row.identity_source_name),
    identity_source_url: nullableString(row.identity_source_url),
    headquarters_address: nullableString(row.headquarters_address),
    headquarters_city: nullableString(row.headquarters_city),
    headquarters_region: nullableString(row.headquarters_region),
    headquarters_postal_code: nullableString(row.headquarters_postal_code),
    headquarters_country: nullableString(row.headquarters_country),
    headquarters_source_name: nullableString(row.headquarters_source_name),
    headquarters_source_url: nullableString(row.headquarters_source_url),
    parent_company_id: nullableString(row.parent_company_id),
    parent_company_name: nullableString(row.parent_company_name),
    parent_source_name: nullableString(row.parent_source_name),
    parent_source_url: nullableString(row.parent_source_url),
    company_type: nullableString(row.company_type),
    enrichment_checked_at: nullableString(row.enrichment_checked_at),
    revenue_amount: nullableNumber(row.revenue_amount),
    revenue_low: nullableNumber(row.revenue_low),
    revenue_high: nullableNumber(row.revenue_high),
    revenue_currency: String(row.revenue_currency ?? 'USD'),
    revenue_year: nullableNumber(row.revenue_year),
    revenue_type: String(row.revenue_type ?? 'unknown') as CompanyAdminProfile['revenue_type'],
    revenue_source_name: nullableString(row.revenue_source_name),
    revenue_source_url: nullableString(row.revenue_source_url),
    revenue_confidence: String(row.revenue_confidence ?? 'unknown') as CompanyAdminProfile['revenue_confidence'],
    relationship_status: String(row.relationship_status ?? 'uncontacted') as CompanyAdminProfile['relationship_status'],
    last_contacted_at: nullableString(row.last_contacted_at),
    next_action_date: nullableString(row.next_action_date),
    account_owner: nullableString(row.account_owner),
    internal_summary: nullableString(row.internal_summary),
    created_at: nullableString(row.created_at) ?? undefined,
    updated_at: nullableString(row.updated_at) ?? undefined,
    created_by: nullableString(row.created_by),
    updated_by: nullableString(row.updated_by),
  }
}

function contactFrom(row: Record<string, unknown>): CompanyAdminContact {
  return {
    contact_id: String(row.contact_id),
    company_id: String(row.company_id),
    name: String(row.name ?? ''),
    title: nullableString(row.title),
    email: nullableString(row.email),
    phone: nullableString(row.phone),
    linkedin_url: nullableString(row.linkedin_url),
    notes: nullableString(row.notes),
    source_name: nullableString(row.source_name),
    source_url: nullableString(row.source_url),
    verified_at: nullableString(row.verified_at),
    active: row.active !== false,
    created_at: nullableString(row.created_at) ?? undefined,
    updated_at: nullableString(row.updated_at) ?? undefined,
  }
}

function activityFrom(row: Record<string, unknown>): CompanyAdminActivity {
  return {
    activity_id: String(row.activity_id),
    company_id: String(row.company_id),
    activity_type: String(row.activity_type ?? 'other'),
    occurred_at: String(row.occurred_at ?? ''),
    contact_id: nullableString(row.contact_id),
    subject: nullableString(row.subject),
    details: nullableString(row.details),
    outcome: nullableString(row.outcome),
    next_action_date: nullableString(row.next_action_date),
    created_at: nullableString(row.created_at) ?? undefined,
    created_by: nullableString(row.created_by),
  }
}

function noteFrom(row: Record<string, unknown>): CompanyAdminNote {
  return {
    note_id: String(row.note_id),
    company_id: String(row.company_id),
    note: String(row.note ?? ''),
    created_at: nullableString(row.created_at) ?? undefined,
    updated_at: nullableString(row.updated_at) ?? undefined,
    created_by: nullableString(row.created_by),
    updated_by: nullableString(row.updated_by),
  }
}

export async function loadCompanyAdminAccess(): Promise<boolean> {
  if (!companyAdminRuntimeEnabled) return false
  const result = await client.from('company_admin_access').select('is_admin').limit(1)
  throwIfError('Unable to verify company-database access', result.error)
  const row = ((result.data ?? []) as Array<Record<string, unknown>>)[0]
  return row?.is_admin === true
}

export async function loadCompanyAdminDirectory(): Promise<CompanyAdminProfile[]> {
  const result = await client.from('company_private_profiles').select('*').order('updated_at', { ascending: false })
  throwIfError('Unable to load private company directory', result.error)
  return ((result.data ?? []) as Array<Record<string, unknown>>).map(profileFrom)
}

export async function loadCompanyAdminSnapshot(companyId: string): Promise<CompanyAdminSnapshot> {
  const [profileResult, contactsResult, activitiesResult, notesResult] = await Promise.all([
    client.from('company_private_profiles').select('*').eq('company_id', companyId).limit(1),
    client.from('company_private_contacts').select('*').eq('company_id', companyId).order('name', { ascending: true }),
    client.from('company_private_activities').select('*').eq('company_id', companyId).order('occurred_at', { ascending: false }),
    client.from('company_private_notes').select('*').eq('company_id', companyId).order('updated_at', { ascending: false }),
  ])
  throwIfError('Unable to load private company profile', profileResult.error)
  throwIfError('Unable to load company contacts', contactsResult.error)
  throwIfError('Unable to load company activity', activitiesResult.error)
  throwIfError('Unable to load company notes', notesResult.error)
  const profileRow = ((profileResult.data ?? []) as Array<Record<string, unknown>>)[0]
  return {
    profile: profileRow ? profileFrom(profileRow) : null,
    contacts: ((contactsResult.data ?? []) as Array<Record<string, unknown>>).map(contactFrom),
    activities: ((activitiesResult.data ?? []) as Array<Record<string, unknown>>).map(activityFrom),
    notes: ((notesResult.data ?? []) as Array<Record<string, unknown>>).map(noteFrom),
  }
}

export type CompanyChangeContext = {
  source?: 'manual' | 'import' | 'system'
  batchId?: string | null
}

export async function saveCompanyAdminProfile(
  companyId: string,
  canonicalName: string,
  patch: Partial<CompanyAdminProfilePatch>,
  context: CompanyChangeContext = {},
): Promise<CompanyAdminProfile> {
  const now = new Date().toISOString()
  const values = {
    ...patch,
    canonical_name: canonicalName,
    updated_at: now,
    last_change_source: context.source ?? 'manual',
    last_change_batch_id: context.batchId ?? null,
  }
  const update = await client.from('company_private_profiles').update(values).eq('company_id', companyId).select('*')
  throwIfError('Unable to update private company profile', update.error)
  const updated = ((update.data ?? []) as Array<Record<string, unknown>>)[0]
  if (updated) return profileFrom(updated)
  const insert = await client.from('company_private_profiles').insert({ company_id: companyId, ...values }).select('*')
  throwIfError('Unable to create private company profile', insert.error)
  const created = ((insert.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!created) throw new Error('Unable to create private company profile: inserted row was not returned')
  return profileFrom(created)
}

export async function saveCompanyAdminContact(
  contactId: string,
  companyId: string,
  values: Omit<CompanyAdminContact, 'contact_id' | 'company_id' | 'created_at' | 'updated_at'>,
  context: CompanyChangeContext = {},
): Promise<CompanyAdminContact> {
  const change = {
    ...values,
    updated_at: new Date().toISOString(),
    last_change_source: context.source ?? 'manual',
    last_change_batch_id: context.batchId ?? null,
  }
  const update = await client.from('company_private_contacts')
    .update(change)
    .eq('contact_id', contactId)
    .eq('company_id', companyId)
    .select('*')
  throwIfError('Unable to update company contact', update.error)
  const updated = ((update.data ?? []) as Array<Record<string, unknown>>)[0]
  if (updated) return contactFrom(updated)

  const insert = await client.from('company_private_contacts').insert({
    contact_id: contactId,
    company_id: companyId,
    ...change,
  }).select('*')
  throwIfError('Unable to add company contact', insert.error)
  const row = ((insert.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!row) throw new Error('Unable to add company contact: inserted row was not returned')
  return contactFrom(row)
}

export async function addCompanyContact(companyId: string, values: Omit<CompanyAdminContact, 'contact_id' | 'company_id' | 'created_at' | 'updated_at'>): Promise<CompanyAdminContact> {
  return saveCompanyAdminContact(crypto.randomUUID(), companyId, values)
}

export async function addCompanyActivity(companyId: string, values: Omit<CompanyAdminActivity, 'activity_id' | 'company_id' | 'created_at' | 'created_by'>): Promise<CompanyAdminActivity> {
  const result = await client.from('company_private_activities').insert({
    activity_id: crypto.randomUUID(),
    company_id: companyId,
    ...values,
    last_change_source: 'manual',
    last_change_batch_id: null,
  }).select('*')
  throwIfError('Unable to add company activity', result.error)
  const row = ((result.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!row) throw new Error('Unable to add company activity: inserted row was not returned')
  return activityFrom(row)
}

export async function addCompanyNote(companyId: string, note: string): Promise<CompanyAdminNote> {
  const result = await client.from('company_private_notes').insert({
    note_id: crypto.randomUUID(),
    company_id: companyId,
    note,
    last_change_source: 'manual',
    last_change_batch_id: null,
  }).select('*')
  throwIfError('Unable to add company note', result.error)
  const row = ((result.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!row) throw new Error('Unable to add company note: inserted row was not returned')
  return noteFrom(row)
}

export async function updateCompanyNote(noteId: string, note: string): Promise<CompanyAdminNote> {
  const result = await client.from('company_private_notes')
    .update({
      note,
      updated_at: new Date().toISOString(),
      last_change_source: 'manual',
      last_change_batch_id: null,
    })
    .eq('note_id', noteId)
    .select('*')
  throwIfError('Unable to update company note', result.error)
  const row = ((result.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!row) throw new Error('Unable to update company note: row was not returned')
  return noteFrom(row)
}


function researchFrom(row: Record<string, unknown>): CompanyResearchQueueItem {
  return {
    company_id: String(row.company_id),
    priority_score: Number(row.priority_score ?? 0),
    priority_reason: String(row.priority_reason ?? ''),
    missing_fields: Array.isArray(row.missing_fields) ? row.missing_fields.map(String) : [],
    status: String(row.status ?? 'unreviewed') as CompanyResearchStatus,
    research_owner: nullableString(row.research_owner),
    last_researched_at: nullableString(row.last_researched_at),
    queued_at: String(row.queued_at ?? ''),
    updated_at: String(row.updated_at ?? ''),
    created_by: nullableString(row.created_by),
    updated_by: nullableString(row.updated_by),
  }
}

function auditFrom(row: Record<string, unknown>): CompanyAuditEntry {
  return {
    change_id: Number(row.change_id ?? 0),
    company_id: String(row.company_id ?? ''),
    entity_type: String(row.entity_type ?? ''),
    entity_id: String(row.entity_id ?? ''),
    operation: String(row.operation ?? ''),
    field_name: String(row.field_name ?? ''),
    old_value: row.old_value,
    new_value: row.new_value,
    change_source: String(row.change_source ?? 'database') as CompanyAuditEntry['change_source'],
    import_batch_id: nullableString(row.import_batch_id),
    changed_at: String(row.changed_at ?? ''),
    changed_by: nullableString(row.changed_by),
  }
}

export async function loadAllCompanyContacts(): Promise<CompanyAdminContact[]> {
  const result = await client.from('company_private_contacts').select('*').order('updated_at', { ascending: false })
  throwIfError('Unable to load private company contacts', result.error)
  return ((result.data ?? []) as Array<Record<string, unknown>>).map(contactFrom)
}

export async function loadAllCompanyActivities(): Promise<CompanyAdminActivity[]> {
  const result = await client.from('company_private_activities').select('*').order('occurred_at', { ascending: false })
  throwIfError('Unable to load private company activities', result.error)
  return ((result.data ?? []) as Array<Record<string, unknown>>).map(activityFrom)
}

export async function loadCompanyResearchQueue(): Promise<CompanyResearchQueueItem[]> {
  const result = await client.from('company_private_research_queue').select('*').order('priority_score', { ascending: false })
  throwIfError('Unable to load company research queue', result.error)
  return ((result.data ?? []) as Array<Record<string, unknown>>).map(researchFrom)
}

export async function saveCompanyResearchQueueItem(
  item: Pick<CompanyResearchQueueItem, 'company_id' | 'priority_score' | 'priority_reason' | 'missing_fields' | 'status' | 'research_owner' | 'last_researched_at'>,
  context: CompanyChangeContext = { source: 'system' },
): Promise<CompanyResearchQueueItem> {
  const values = {
    priority_score: item.priority_score,
    priority_reason: item.priority_reason,
    missing_fields: item.missing_fields,
    status: item.status,
    research_owner: item.research_owner,
    last_researched_at: item.last_researched_at,
    updated_at: new Date().toISOString(),
    last_change_source: context.source ?? 'system',
    last_change_batch_id: context.batchId ?? null,
  }
  const update = await client.from('company_private_research_queue').update(values).eq('company_id', item.company_id).select('*')
  throwIfError('Unable to update company research queue', update.error)
  const updated = ((update.data ?? []) as Array<Record<string, unknown>>)[0]
  if (updated) return researchFrom(updated)

  const insert = await client.from('company_private_research_queue').insert({ company_id: item.company_id, ...values }).select('*')
  throwIfError('Unable to add company research queue item', insert.error)
  const created = ((insert.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!created) throw new Error('Unable to add company research queue item: row was not returned')
  return researchFrom(created)
}

export async function deleteCompanyResearchQueueItem(companyId: string): Promise<void> {
  const result = await client.from('company_private_research_queue').delete().eq('company_id', companyId)
  throwIfError('Unable to remove stale company research queue item', result.error)
}

export async function syncCompanyResearchQueue(candidates: Array<{
  company_id: string
  canonical_name: string
  priority_score: number
  priority_reason: string
  missing_fields: string[]
}>): Promise<void> {
  if (candidates.length !== 100) {
    throw new Error(`Research queue sync requires exactly 100 ranked master companies; received ${candidates.length}`)
  }

  const current = await loadCompanyResearchQueue()
  const currentById = new Map(current.map(item => [item.company_id, item]))
  const desiredIds = new Set(candidates.map(candidate => candidate.company_id))

  for (let index = 0; index < candidates.length; index += 5) {
    const chunk = candidates.slice(index, index + 5)
    await Promise.all(chunk.map(async candidate => {
      const existing = currentById.get(candidate.company_id)
      await saveCompanyAdminProfile(candidate.company_id, candidate.canonical_name, {}, { source: 'system', batchId: 'research-queue-sync' })
      await saveCompanyResearchQueueItem({
        company_id: candidate.company_id,
        priority_score: candidate.priority_score,
        priority_reason: candidate.priority_reason,
        missing_fields: candidate.missing_fields,
        status: existing?.status ?? 'unreviewed',
        research_owner: existing?.research_owner ?? null,
        last_researched_at: existing?.last_researched_at ?? null,
      }, { source: 'system', batchId: 'research-queue-sync' })
    }))
  }

  const stale = current.filter(item => !desiredIds.has(item.company_id))
  for (let index = 0; index < stale.length; index += 10) {
    await Promise.all(stale.slice(index, index + 10).map(item => deleteCompanyResearchQueueItem(item.company_id)))
  }
}

export async function loadCompanyAuditLog(companyId: string, limit = 80): Promise<CompanyAuditEntry[]> {
  const result = await client.from('company_private_change_log').select('*')
    .eq('company_id', companyId).order('changed_at', { ascending: false }).limit(limit)
  throwIfError('Unable to load company change history', result.error)
  return ((result.data ?? []) as Array<Record<string, unknown>>).map(auditFrom)
}
