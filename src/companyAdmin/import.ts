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
  'contact_role',
  'primary_contact',
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

const revenueTypes = new Set(['reported', 'estimated', 'range', 'unknown'])
const revenueConfidences = new Set(['confirmed', 'strong', 'verify', 'unknown'])
const contactRoles = new Set([
  'decision-maker','champion','technical','procurement','finance','executive','other',
])

function optionalText(value: unknown, context: string): string | null {
  if (value == null || value === '') return null
  if (typeof value !== 'string') throw new Error(`${context} must be text`)
  const text = value.trim()
  return text || null
}

function requireHttps(value: unknown, context: string): string {
  const text = requiredText(value, context)
  let url: URL
  try {
    url = new URL(text)
  } catch {
    throw new Error(`${context} must be a valid HTTPS URL`)
  }
  if (url.protocol !== 'https:') throw new Error(`${context} must use HTTPS`)
  return text
}

function requireSource(profile: Record<string, unknown>, prefix: string, context: string) {
  requiredText(profile[`${prefix}_source_name`], `${context}.${prefix}_source_name`)
  requireHttps(profile[`${prefix}_source_url`], `${context}.${prefix}_source_url`)
}

function validateDate(value: unknown, context: string) {
  const text = optionalText(value, context)
  if (!text) return
  if (Number.isNaN(Date.parse(text))) throw new Error(`${context} must be a valid date/time`)
}

function validateNumber(value: unknown, context: string): number | null {
  if (value == null || value === '') return null
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    throw new Error(`${context} must be a non-negative number`)
  }
  return value
}

function validateProfile(profile: Record<string, unknown>, known: Map<string, string>, context: string) {
  const website = optionalText(profile.website, `${context}.website`)
  if (website) {
    requireHttps(website, `${context}.website`)
    requireSource(profile, 'website', context)
  }

  const hasIdentity = ['legal_name', 'company_type'].some(key => optionalText(profile[key], `${context}.${key}`))
  if (hasIdentity) requireSource(profile, 'identity', context)

  const hasHeadquarters = [
    'headquarters_address', 'headquarters_city', 'headquarters_region',
    'headquarters_postal_code', 'headquarters_country',
  ].some(key => optionalText(profile[key], `${context}.${key}`))
  if (hasHeadquarters) requireSource(profile, 'headquarters', context)

  const parentId = optionalText(profile.parent_company_id, `${context}.parent_company_id`)
  const parentName = optionalText(profile.parent_company_name, `${context}.parent_company_name`)
  if (parentId || parentName) {
    if (parentId && !known.has(parentId)) throw new Error(`${context}.parent_company_id is not a known TowerSignal firm_id: ${parentId}`)
    requireSource(profile, 'parent', context)
  }

  const rollupId = optionalText(profile.rollup_company_id, `${context}.rollup_company_id`)
  const rollupName = optionalText(profile.rollup_name, `${context}.rollup_name`)
  if (rollupId || rollupName) {
    if (rollupId && !known.has(rollupId)) throw new Error(`${context}.rollup_company_id is not a known TowerSignal firm_id: ${rollupId}`)
    requireSource(profile, 'rollup', context)
  }

  const amount = validateNumber(profile.revenue_amount, `${context}.revenue_amount`)
  const low = validateNumber(profile.revenue_low, `${context}.revenue_low`)
  const high = validateNumber(profile.revenue_high, `${context}.revenue_high`)
  if (low != null && high != null && low > high) throw new Error(`${context} revenue range low cannot exceed high`)
  const revenueType = profile.revenue_type == null ? 'unknown' : optionalText(profile.revenue_type, `${context}.revenue_type`) ?? 'unknown'
  if (!revenueTypes.has(revenueType)) throw new Error(`${context}.revenue_type is invalid`)
  const revenueConfidence = profile.revenue_confidence == null ? 'unknown' : optionalText(profile.revenue_confidence, `${context}.revenue_confidence`) ?? 'unknown'
  if (!revenueConfidences.has(revenueConfidence)) throw new Error(`${context}.revenue_confidence is invalid`)
  if (revenueType === 'range' && (low == null || high == null)) throw new Error(`${context} range revenue requires revenue_low and revenue_high`)
  if (amount != null || low != null || high != null) {
    const year = profile.revenue_year
    if (typeof year !== 'number' || !Number.isInteger(year) || year < 1900 || year > 2100) {
      throw new Error(`${context}.revenue_year is required for sourced revenue`)
    }
    requiredText(profile.revenue_source_name, `${context}.revenue_source_name`)
    requireHttps(profile.revenue_source_url, `${context}.revenue_source_url`)
    if (revenueType === 'unknown') throw new Error(`${context}.revenue_type cannot be unknown when a revenue value is present`)
  }

  const currency = optionalText(profile.revenue_currency, `${context}.revenue_currency`)
  if (currency && !/^[A-Z]{3}$/.test(currency)) throw new Error(`${context}.revenue_currency must be a three-letter uppercase code`)

  validateDate(profile.enrichment_checked_at, `${context}.enrichment_checked_at`)
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

    const profileContext = `companies[${index}].profile`
    const profile = record(value.profile ?? {}, profileContext)
    checkAllowedKeys(profile, profileKeys as Set<string>, profileContext)
    validateProfile(profile, known, profileContext)

    const contactsRaw = value.contacts ?? []
    if (!Array.isArray(contactsRaw)) throw new Error(`companies[${index}].contacts must be an array`)
    const contactIds = new Set<string>()
    const contacts = contactsRaw.map((rawContact, contactIndex) => {
      const contact = record(rawContact, `companies[${index}].contacts[${contactIndex}]`)
      checkAllowedKeys(contact, contactKeys as Set<string>, `companies[${index}].contacts[${contactIndex}]`)
      const contactContext = `companies[${index}].contacts[${contactIndex}]`
      const contactId = requiredText(contact.contact_id, `${contactContext}.contact_id`)
      const name = requiredText(contact.name, `${contactContext}.name`)
      requiredText(contact.source_name, `${contactContext}.source_name`)
      requireHttps(contact.source_url, `${contactContext}.source_url`)
      validateDate(contact.verified_at, `${contactContext}.verified_at`)
      const contactRole = optionalText(contact.contact_role, `${contactContext}.contact_role`)
      if (contactRole && !contactRoles.has(contactRole)) throw new Error(`${contactContext}.contact_role is invalid`)
      if (contact.primary_contact != null && typeof contact.primary_contact !== 'boolean') {
        throw new Error(`${contactContext}.primary_contact must be boolean`)
      }
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
        contact_role: contactRole as ContactWrite['contact_role'],
        primary_contact: contact.primary_contact === true,
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
  const batchId = bundle.generated_at ?? crypto.randomUUID()
  for (const company of bundle.companies) {
    await saveCompanyAdminProfile(company.company_id, company.canonical_name, company.profile as CompanyAdminProfilePatch, { source: 'import', batchId })
    for (const contact of company.contacts ?? []) {
      const { contact_id, ...values } = contact
      await saveCompanyAdminContact(contact_id, company.company_id, values, { source: 'import', batchId })
      contacts += 1
    }
  }
  return { companies: bundle.companies.length, contacts }
}
