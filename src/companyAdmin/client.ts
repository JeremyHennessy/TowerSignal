import { createClient } from '@neondatabase/neon-js'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminNote,
  CompanyAdminProfile,
  CompanyAdminProfilePatch,
  CompanyAdminSnapshot,
} from '../types/companyAdmin'

const DEFAULT_AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const DEFAULT_DATA_API_URL = 'https://ep-silent-moon-au2icaki.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'

const client = createClient({
  auth: { url: import.meta.env.VITE_NEON_AUTH_URL || DEFAULT_AUTH_URL },
  dataApi: { url: import.meta.env.VITE_NEON_DATA_API_URL || DEFAULT_DATA_API_URL },
})

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
    website: nullableString(row.website),
    headquarters_address: nullableString(row.headquarters_address),
    headquarters_city: nullableString(row.headquarters_city),
    headquarters_region: nullableString(row.headquarters_region),
    headquarters_postal_code: nullableString(row.headquarters_postal_code),
    headquarters_country: nullableString(row.headquarters_country),
    parent_company_id: nullableString(row.parent_company_id),
    parent_company_name: nullableString(row.parent_company_name),
    company_type: nullableString(row.company_type),
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

export async function saveCompanyAdminProfile(
  companyId: string,
  canonicalName: string,
  patch: CompanyAdminProfilePatch,
): Promise<CompanyAdminProfile> {
  const now = new Date().toISOString()
  const values = { ...patch, canonical_name: canonicalName, updated_at: now }
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

export async function addCompanyContact(companyId: string, values: Omit<CompanyAdminContact, 'contact_id' | 'company_id' | 'created_at' | 'updated_at'>): Promise<CompanyAdminContact> {
  const result = await client.from('company_private_contacts').insert({
    contact_id: crypto.randomUUID(),
    company_id: companyId,
    ...values,
  }).select('*')
  throwIfError('Unable to add company contact', result.error)
  const row = ((result.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!row) throw new Error('Unable to add company contact: inserted row was not returned')
  return contactFrom(row)
}

export async function addCompanyActivity(companyId: string, values: Omit<CompanyAdminActivity, 'activity_id' | 'company_id' | 'created_at' | 'created_by'>): Promise<CompanyAdminActivity> {
  const result = await client.from('company_private_activities').insert({
    activity_id: crypto.randomUUID(),
    company_id: companyId,
    ...values,
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
  }).select('*')
  throwIfError('Unable to add company note', result.error)
  const row = ((result.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!row) throw new Error('Unable to add company note: inserted row was not returned')
  return noteFrom(row)
}

export async function updateCompanyNote(noteId: string, note: string): Promise<CompanyAdminNote> {
  const result = await client.from('company_private_notes')
    .update({ note, updated_at: new Date().toISOString() })
    .eq('note_id', noteId)
    .select('*')
  throwIfError('Unable to update company note', result.error)
  const row = ((result.data ?? []) as Array<Record<string, unknown>>)[0]
  if (!row) throw new Error('Unable to update company note: row was not returned')
  return noteFrom(row)
}
