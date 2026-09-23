import {
  loadCompanyAdminAccess,
  saveCompanyAdminContact,
  saveCompanyAdminProfile,
} from './client'
import type {
  CompanyAdminContact,
  CompanyAdminProfilePatch,
} from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'

export const COMPANY_ADMIN_IMPORT_SCHEMA = 'TOWERSIGNAL_PRIVATE_COMPANY_IMPORT_V1'

type ContactWrite = Omit<CompanyAdminContact, 'company_id' | 'created_at' | 'updated_at'>

export interface CompanyAdminImportCompany {
  company_id: string
  canonical_name: string
  profile: Partial<CompanyAdminProfilePatch>
  contacts?: ContactWrite[]
}

export interface CompanyAdminImportBundle {
  schema: typeof COMPANY_ADMIN_IMPORT_SCHEMA
  generated_at?: string
  companies: CompanyAdminImportCompany[]
}

const profileKeys = new Set<keyof CompanyAdminProfilePatch>([
  'legal_name',
  'rollup_name',
  'rollup_company_id',
  'rollup_source_name',
  'rollup_source_url',
  'website',
  'website_source_name',
  'website_source_url',
  'identity_source_name',
  'identity_source_url',
  'headquarters_address',
  'headquarters_city',
  'headquarters_region',
  'headquarters_postal_code',
  'headquarters_country',
  'headquarters_source_name',
  'headquarters_source_url',
  'parent_company_id',
  'parent_company_name',
  'parent_source_name',
  'parent_source_url',
  'company_type',
  'enrichment_checked_at',
  'revenue_amount',
  'revenue_low',
  'revenue_high',
  'revenue_currency',
  'revenue_year',
  'revenue_type',
  'revenue_source_name',
  'revenue_source_url',
  'revenue_confidence',
  'relationship_status',
  'last_contacted_at',
  'next_action_date',
  'account_owner',
  'internal_summary',
])

const contactKeys = new Set<keyof ContactWrite>([
  'contact_id',
  'name',
  'title',
  'email',
  'phone',
  'linkedin_url',
  'notes',
  'source_name',
  'source_url',
  'verified_at',
  'active',
])

function record(value: unknown, context: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${context} must be an object`)
  return value as Record<string, unknown>
}

function requiredText(value: unknown, context: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${context} is required`)
  return value.trim()
}

function checkAllowedKeys(value: Record<string, unknown>, allowed: Set<string>, context: string) {
  const unknown = Object.keys(value).filter(key => !allowed.has(key))
  if (unknown.length) throw new Error(`${context} contains unsupported fields: ${unknown.join(', ')}`)
}

export function parseCompanyAdminImport(text: string, knownFirms: KnownFirmSummaryRecord[]): CompanyAdminImportBundle {
  const root = record(JSON.parse(text), 'Import bundle')
  if (root.schema !== COMPANY_ADMIN_IMPORT_SCHEMA) {
    throw new Error(`Import schema must be ${COMPANY_ADMIN_IMPORT_SCHEMA}`)
  }
  if (!Array.isArray(root.companies) || root.companies.length === 0) throw new Error('Import bundle must contain companies[]')

  const known = new Map(knownFirms.map(firm => [firm.firm_id, firm.canonical_name]))
  const seen = new Set<string>()
  const companies = root.companies.map((raw, index) => {
    const value = record(raw, `companies[${index}]`)
    const companyId = requiredText(value.company_id, `companies[${index}].company_id`)
    const canonicalName = requiredText(value.canonical_name, `companies[${index}].canonical_name`)
    const expectedName = known.get(companyId)
    if (!expectedName) throw new Error(`Unknown TowerSignal firm_id: ${companyId}`)
    if (expectedName !== canonicalName) {
      throw new Error(`Canonical-name mismatch for ${companyId}: expected "${expectedName}"`)
    }
    if (seen.has(companyId)) throw new Error(`Duplicate company_id in import: ${companyId}`)
    seen.add(companyId)

    const profile = record(value.profile ?? {}, `companies[${index}].profile`)
    checkAllowedKeys(profile, profileKeys as Set<string>, `companies[${index}].profile`)

    const contactsRaw = value.contacts ?? []
    if (!Array.isArray(contactsRaw)) throw new Error(`companies[${index}].contacts must be an array`)
    const contactIds = new Set<string>()
    const contacts = contactsRaw.map((rawContact, contactIndex) => {
      const contact = record(rawContact, `companies[${index}].contacts[${contactIndex}]`)
      checkAllowedKeys(contact, contactKeys as Set<string>, `companies[${index}].contacts[${contactIndex}]`)
      const contactId = requiredText(contact.contact_id, `companies[${index}].contacts[${contactIndex}].contact_id`)
      const name = requiredText(contact.name, `companies[${index}].contacts[${contactIndex}].name`)
      if (contactIds.has(contactId)) throw new Error(`Duplicate contact_id in company ${companyId}: ${contactId}`)
      contactIds.add(contactId)
      return {
        contact_id: contactId,
        name,
        title: typeof contact.title === 'string' ? contact.title : null,
        email: typeof contact.email === 'string' ? contact.email : null,
        phone: typeof contact.phone === 'string' ? contact.phone : null,
        linkedin_url: typeof contact.linkedin_url === 'string' ? contact.linkedin_url : null,
        notes: typeof contact.notes === 'string' ? contact.notes : null,
        source_name: typeof contact.source_name === 'string' ? contact.source_name : null,
        source_url: typeof contact.source_url === 'string' ? contact.source_url : null,
        verified_at: typeof contact.verified_at === 'string' ? contact.verified_at : null,
        active: contact.active !== false,
      } satisfies ContactWrite
    })

    return {
      company_id: companyId,
      canonical_name: canonicalName,
      profile: profile as Partial<CompanyAdminProfilePatch>,
      contacts,
    }
  })

  return {
    schema: COMPANY_ADMIN_IMPORT_SCHEMA,
    generated_at: typeof root.generated_at === 'string' ? root.generated_at : undefined,
    companies,
  }
}

export async function applyCompanyAdminImport(bundle: CompanyAdminImportBundle): Promise<{ companies: number; contacts: number }> {
  if (!await loadCompanyAdminAccess()) throw new Error('Admin company-database access is required')

  let contacts = 0
  for (const company of bundle.companies) {
    await saveCompanyAdminProfile(company.company_id, company.canonical_name, company.profile as CompanyAdminProfilePatch)
    for (const contact of company.contacts ?? []) {
      const { contact_id, ...values } = contact
      await saveCompanyAdminContact(contact_id, company.company_id, values)
      contacts += 1
    }
  }
  return { companies: bundle.companies.length, contacts }
}
