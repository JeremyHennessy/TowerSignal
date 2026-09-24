import { useEffect, useMemo, useState } from 'react'
import {
  addCompanyActivity,
  addCompanyContact,
  addCompanyNote,
  loadCompanyAdminAccess,
  loadCompanyAdminSnapshot,
  saveCompanyAdminProfile,
  saveCompanyAdminContact,
  updateCompanyNote,
} from '../companyAdmin/client'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminNote,
  CompanyAdminProfile,
  CompanyAdminProfilePatch,
  CompanyRelationshipStatus,
} from '../types/companyAdmin'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

const relationshipStatuses: CompanyRelationshipStatus[] = [
  'uncontacted', 'researching', 'outreach-planned', 'contacted', 'engaged', 'opportunity', 'customer', 'not-pursuing',
]

function emptyProfile(): CompanyAdminProfilePatch {
  return {
    legal_name: null,
    rollup_name: null,
    rollup_company_id: null,
    rollup_source_name: null,
    rollup_source_url: null,
    website: null,
    website_source_name: null,
    website_source_url: null,
    identity_source_name: null,
    identity_source_url: null,
    headquarters_address: null,
    headquarters_city: null,
    headquarters_region: null,
    headquarters_postal_code: null,
    headquarters_country: null,
    headquarters_source_name: null,
    headquarters_source_url: null,
    parent_company_id: null,
    parent_company_name: null,
    parent_source_name: null,
    parent_source_url: null,
    company_type: null,
    enrichment_checked_at: null,
    revenue_amount: null,
    revenue_low: null,
    revenue_high: null,
    revenue_currency: 'USD',
    revenue_year: null,
    revenue_type: 'unknown',
    revenue_source_name: null,
    revenue_source_url: null,
    revenue_confidence: 'unknown',
    relationship_status: 'uncontacted',
    last_contacted_at: null,
    next_action_date: null,
    account_owner: null,
    internal_summary: null,
  }
}

function patchFrom(profile: CompanyAdminProfile | null): CompanyAdminProfilePatch {
  if (!profile) return emptyProfile()
  const patch = { ...profile } as Partial<CompanyAdminProfile>
  delete patch.company_id
  delete patch.canonical_name
  delete patch.created_at
  delete patch.updated_at
  delete patch.created_by
  delete patch.updated_by
  return patch as CompanyAdminProfilePatch
}

function text(value: string): string | null {
  const trimmed = value.trim()
  return trimmed || null
}

function numberValue(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeProfilePatch(value: CompanyAdminProfilePatch): CompanyAdminProfilePatch {
  return {
    ...value,
    legal_name: text(value.legal_name ?? ''),
    rollup_name: text(value.rollup_name ?? ''),
    rollup_company_id: text(value.rollup_company_id ?? ''),
    rollup_source_name: text(value.rollup_source_name ?? ''),
    rollup_source_url: text(value.rollup_source_url ?? ''),
    website: text(value.website ?? ''),
    website_source_name: text(value.website_source_name ?? ''),
    website_source_url: text(value.website_source_url ?? ''),
    identity_source_name: text(value.identity_source_name ?? ''),
    identity_source_url: text(value.identity_source_url ?? ''),
    headquarters_address: text(value.headquarters_address ?? ''),
    headquarters_city: text(value.headquarters_city ?? ''),
    headquarters_region: text(value.headquarters_region ?? ''),
    headquarters_postal_code: text(value.headquarters_postal_code ?? ''),
    headquarters_country: text(value.headquarters_country ?? ''),
    headquarters_source_name: text(value.headquarters_source_name ?? ''),
    headquarters_source_url: text(value.headquarters_source_url ?? ''),
    parent_company_id: text(value.parent_company_id ?? ''),
    parent_company_name: text(value.parent_company_name ?? ''),
    parent_source_name: text(value.parent_source_name ?? ''),
    parent_source_url: text(value.parent_source_url ?? ''),
    company_type: text(value.company_type ?? ''),
    revenue_currency: value.revenue_currency.trim().toUpperCase().slice(0, 3) || 'USD',
    revenue_source_name: text(value.revenue_source_name ?? ''),
    revenue_source_url: text(value.revenue_source_url ?? ''),
    next_action_date: text(value.next_action_date ?? ''),
    account_owner: text(value.account_owner ?? ''),
    internal_summary: text(value.internal_summary ?? ''),
  }
}

function localDateTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

function relationshipLabel(value: string): string {
  return value.replaceAll('-', ' ').replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function formatRevenue(profile: CompanyAdminProfilePatch): string {
  if (profile.revenue_type === 'range' && profile.revenue_low != null && profile.revenue_high != null) {
    return `${money.format(profile.revenue_low)}–${money.format(profile.revenue_high)}`
  }
  return profile.revenue_amount == null ? 'Not recorded' : money.format(profile.revenue_amount)
}

export function CompanyAdminPanel({ companyId, canonicalName }: { companyId: string; canonicalName: string }) {
  const [checking, setChecking] = useState(true)
  const [allowed, setAllowed] = useState(false)
  const [profile, setProfile] = useState<CompanyAdminProfilePatch>(emptyProfile())
  const [contacts, setContacts] = useState<CompanyAdminContact[]>([])
  const [activities, setActivities] = useState<CompanyAdminActivity[]>([])
  const [notes, setNotes] = useState<CompanyAdminNote[]>([])
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({})
  const [newNote, setNewNote] = useState('')
  const [contactName, setContactName] = useState('')
  const [contactTitle, setContactTitle] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [contactLinkedin, setContactLinkedin] = useState('')
  const [contactSourceName, setContactSourceName] = useState('')
  const [editingContact, setEditingContact] = useState<CompanyAdminContact | null>(null)
  const [contactSourceUrl, setContactSourceUrl] = useState('')
  const [contactVerifiedAt, setContactVerifiedAt] = useState('')
  const [activityType, setActivityType] = useState('email')
  const [activityDate, setActivityDate] = useState(() => localDateTime(new Date().toISOString()))
  const [activityContactId, setActivityContactId] = useState('')
  const [activitySubject, setActivitySubject] = useState('')
  const [activityOutcome, setActivityOutcome] = useState('')
  const [activityDetails, setActivityDetails] = useState('')
  const [activityNextAction, setActivityNextAction] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<string | null>(null)

  const reload = async () => {
    const snapshot = await loadCompanyAdminSnapshot(companyId)
    setProfile(patchFrom(snapshot.profile))
    setContacts(snapshot.contacts)
    setActivities(snapshot.activities)
    setNotes(snapshot.notes)
    setNoteDrafts(Object.fromEntries(snapshot.notes.map(note => [note.note_id, note.note])))
  }

  useEffect(() => {
    let cancelled = false
    setChecking(true)
    setAllowed(false)
    setError(null)
    loadCompanyAdminAccess()
      .then(async isAdmin => {
        if (cancelled || !isAdmin) return
        setAllowed(true)
        const snapshot = await loadCompanyAdminSnapshot(companyId)
        if (cancelled) return
        setProfile(patchFrom(snapshot.profile))
        setContacts(snapshot.contacts)
        setActivities(snapshot.activities)
        setNotes(snapshot.notes)
        setNoteDrafts(Object.fromEntries(snapshot.notes.map(note => [note.note_id, note.note])))
      })
      .catch(err => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unable to load private company database')
      })
      .finally(() => { if (!cancelled) setChecking(false) })
    return () => { cancelled = true }
  }, [companyId])

  const contactById = useMemo(() => new Map(contacts.map(contact => [contact.contact_id, contact])), [contacts])

  const locationSummary = useMemo(() => [
    profile.headquarters_city,
    profile.headquarters_region,
    profile.headquarters_country,
  ].filter(Boolean).join(', ') || 'Not recorded', [profile.headquarters_city, profile.headquarters_region, profile.headquarters_country])

  const saveProfile = async () => {
    setBusy(true)
    setError(null)
    try {
      const saved = await saveCompanyAdminProfile(companyId, canonicalName, normalizeProfilePatch(profile))
      setProfile(patchFrom(saved))
      setSavedAt(new Date().toISOString())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save company profile')
    } finally {
      setBusy(false)
    }
  }

  const addContact = async () => {
    if (!contactName.trim()) return
    setBusy(true)
    setError(null)
    try {
      const savedProfile = await saveCompanyAdminProfile(companyId, canonicalName, normalizeProfilePatch(profile))
      setProfile(patchFrom(savedProfile))
      await addCompanyContact(companyId, {
        name: contactName.trim(),
        title: text(contactTitle),
        email: text(contactEmail),
        phone: text(contactPhone),
        linkedin_url: text(contactLinkedin),
        notes: null,
        source_name: text(contactSourceName),
        source_url: text(contactSourceUrl),
        verified_at: contactVerifiedAt ? new Date(contactVerifiedAt).toISOString() : null,
        active: true,
      })
      setContactName('')
      setContactTitle('')
      setContactEmail('')
      setContactPhone('')
      setContactLinkedin('')
      setContactSourceName('')
      setContactSourceUrl('')
      setContactVerifiedAt('')
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to add contact')
    } finally {
      setBusy(false)
    }
  }

  const saveContact = async () => {
    if (!editingContact || !editingContact.name.trim()) return
    setBusy(true)
    setError(null)
    try {
      await saveCompanyAdminContact(editingContact.contact_id, companyId, {
        name: editingContact.name.trim(),
        title: text(editingContact.title ?? ''),
        email: text(editingContact.email ?? ''),
        phone: text(editingContact.phone ?? ''),
        linkedin_url: text(editingContact.linkedin_url ?? ''),
        notes: text(editingContact.notes ?? ''),
        source_name: text(editingContact.source_name ?? ''),
        source_url: text(editingContact.source_url ?? ''),
        verified_at: editingContact.verified_at,
        active: editingContact.active,
      })
      setEditingContact(null)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update contact')
    } finally {
      setBusy(false)
    }
  }

  const addActivity = async () => {
    if (!activityDate) return
    setBusy(true)
    setError(null)
    try {
      const normalizedProfile = normalizeProfilePatch(profile)\n      await saveCompanyAdminProfile(companyId, canonicalName, normalizedProfile)
      const occurredAt = new Date(activityDate).toISOString()
      await addCompanyActivity(companyId, {
        activity_type: activityType,
        occurred_at: occurredAt,
        contact_id: text(activityContactId),
        subject: text(activitySubject),
        details: text(activityDetails),
        outcome: text(activityOutcome),
        next_action_date: text(activityNextAction),
      })
      const nextProfile = {
        ...normalizedProfile,
        relationship_status: profile.relationship_status === 'uncontacted' ? 'contacted' as const : profile.relationship_status,
        last_contacted_at: occurredAt,
        next_action_date: text(activityNextAction) ?? profile.next_action_date,
      }
      await saveCompanyAdminProfile(companyId, canonicalName, nextProfile)
      setProfile(nextProfile)
      setActivitySubject('')
      setActivityOutcome('')
      setActivityDetails('')
      setActivityNextAction('')
      setActivityDate(localDateTime(new Date().toISOString()))
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to log company activity')
    } finally {
      setBusy(false)
    }
  }

  const addNote = async () => {
    if (!newNote.trim()) return
    setBusy(true)
    setError(null)
    try {
      const savedProfile = await saveCompanyAdminProfile(companyId, canonicalName, normalizeProfilePatch(profile))
      setProfile(patchFrom(savedProfile))
      await addCompanyNote(companyId, newNote.trim())
      setNewNote('')
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to add note')
    } finally {
      setBusy(false)
    }
  }

  const saveNote = async (noteId: string) => {
    const value = noteDrafts[noteId]?.trim()
    if (!value) return
    setBusy(true)
    setError(null)
    try {
      await updateCompanyNote(noteId, value)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update note')
    } finally {
      setBusy(false)
    }
  }

  if (checking || !allowed) return null

  return <section className="company-admin-panel" aria-label="Admin company database">
    <div className="company-admin-heading">
      <div>
        <span className="page-kicker">Admin only · private company database</span>
        <h2>Company master &amp; relationship record</h2>
        <p>Private enrichment and CRM data. Source-backed TowerSignal evidence below remains unchanged.</p>
      </div>
      <div className="company-admin-save-state">
        <span>{relationshipLabel(profile.relationship_status)}</span>
        {savedAt && <small>Saved {new Date(savedAt).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })}</small>}
        <button onClick={saveProfile} disabled={busy}>{busy ? 'Saving…' : 'Save company'}</button>
      </div>
    </div>

    {error && <div className="company-admin-error"><strong>Private company database error.</strong><span>{error}</span></div>}

    <div className="company-admin-summary">
      <article><small>Rollup</small><strong>{profile.rollup_name || canonicalName}</strong><span>{profile.rollup_company_id || 'No explicit rollup ID'}</span></article>
      <article><small>HQ</small><strong>{locationSummary}</strong><span>{profile.headquarters_address || 'Street address not recorded'}</span></article>
      <article><small>Parent</small><strong>{profile.parent_company_name || 'Independent / not recorded'}</strong><span>{profile.parent_company_id || 'No parent ID'}</span></article>
      <article><small>Revenue</small><strong>{formatRevenue(profile)}</strong><span>{profile.revenue_year ? `${profile.revenue_year} · ${relationshipLabel(profile.revenue_type)}` : 'Year/source not recorded'}</span></article>
    </div>

    <div className="company-admin-grid">
      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Company identity &amp; structure</strong><span>Editable private enrichment</span></div>
        <div className="company-admin-form-grid">
          <label><span>Legal name</span><input value={profile.legal_name ?? ''} onChange={event => setProfile(value => ({ ...value, legal_name:event.target.value }))} /></label>
          <label><span>Rolled-up normalized name</span><input value={profile.rollup_name ?? ''} onChange={event => setProfile(value => ({ ...value, rollup_name:event.target.value }))} /></label>
          <label><span>Rollup company ID</span><input value={profile.rollup_company_id ?? ''} onChange={event => setProfile(value => ({ ...value, rollup_company_id:event.target.value }))} placeholder="Explicit only; never inferred" /></label>
          <label><span>Website</span><input type="url" value={profile.website ?? ''} onChange={event => setProfile(value => ({ ...value, website:event.target.value }))} placeholder="https://…" /></label>
          <label><span>Company type</span><input value={profile.company_type ?? ''} onChange={event => setProfile(value => ({ ...value, company_type:event.target.value }))} /></label>
          <label><span>Parent company</span><input value={profile.parent_company_name ?? ''} onChange={event => setProfile(value => ({ ...value, parent_company_name:event.target.value }))} /></label>
          <label><span>Parent company ID</span><input value={profile.parent_company_id ?? ''} onChange={event => setProfile(value => ({ ...value, parent_company_id:event.target.value }))} /></label>
        </div>
        <div className="company-admin-form-grid address-grid">
          <label className="wide"><span>HQ street address</span><input value={profile.headquarters_address ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_address:event.target.value }))} /></label>
          <label><span>City</span><input value={profile.headquarters_city ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_city:event.target.value }))} /></label>
          <label><span>State / region</span><input value={profile.headquarters_region ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_region:event.target.value }))} /></label>
          <label><span>Postal code</span><input value={profile.headquarters_postal_code ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_postal_code:event.target.value }))} /></label>
          <label><span>Country</span><input value={profile.headquarters_country ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_country:event.target.value }))} /></label>
        </div>
        <div className="company-admin-card-heading"><strong>Profile provenance</strong><span>Record the evidence used for every private enrichment decision</span></div>
        <div className="company-admin-form-grid">
          <label><span>Identity source</span><input value={profile.identity_source_name ?? ''} onChange={event => setProfile(value => ({ ...value, identity_source_name:event.target.value }))} placeholder="Official company site, filing…" /></label>
          <label className="wide"><span>Identity source URL</span><input type="url" value={profile.identity_source_url ?? ''} onChange={event => setProfile(value => ({ ...value, identity_source_url:event.target.value }))} /></label>
          <label><span>Website source</span><input value={profile.website_source_name ?? ''} onChange={event => setProfile(value => ({ ...value, website_source_name:event.target.value }))} /></label>
          <label className="wide"><span>Website source URL</span><input type="url" value={profile.website_source_url ?? ''} onChange={event => setProfile(value => ({ ...value, website_source_url:event.target.value }))} /></label>
          <label><span>Rollup source</span><input value={profile.rollup_source_name ?? ''} onChange={event => setProfile(value => ({ ...value, rollup_source_name:event.target.value }))} /></label>
          <label className="wide"><span>Rollup source URL</span><input type="url" value={profile.rollup_source_url ?? ''} onChange={event => setProfile(value => ({ ...value, rollup_source_url:event.target.value }))} placeholder="Evidence for explicit private rollup" /></label>
          <label><span>HQ source</span><input value={profile.headquarters_source_name ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_source_name:event.target.value }))} /></label>
          <label className="wide"><span>HQ source URL</span><input type="url" value={profile.headquarters_source_url ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_source_url:event.target.value }))} /></label>
          <label><span>Parent source</span><input value={profile.parent_source_name ?? ''} onChange={event => setProfile(value => ({ ...value, parent_source_name:event.target.value }))} /></label>
          <label className="wide"><span>Parent source URL</span><input type="url" value={profile.parent_source_url ?? ''} onChange={event => setProfile(value => ({ ...value, parent_source_url:event.target.value }))} /></label>
          <label><span>Enrichment checked</span><input type="datetime-local" value={localDateTime(profile.enrichment_checked_at)} onChange={event => setProfile(value => ({ ...value, enrichment_checked_at:event.target.value ? new Date(event.target.value).toISOString() : null }))} /></label>
        </div>
      </section>

      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Revenue</strong><span>Keep source and confidence with every number</span></div>
        <div className="company-admin-form-grid">
          <label><span>Revenue type</span><select value={profile.revenue_type} onChange={event => setProfile(value => ({ ...value, revenue_type:event.target.value as CompanyAdminProfilePatch['revenue_type'] }))}><option value="unknown">Unknown</option><option value="reported">Reported</option><option value="estimated">Estimated</option><option value="range">Range</option></select></label>
          <label><span>Amount</span><input type="number" min="0" value={profile.revenue_amount ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_amount:numberValue(event.target.value) }))} /></label>
          <label><span>Range low</span><input type="number" min="0" value={profile.revenue_low ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_low:numberValue(event.target.value) }))} /></label>
          <label><span>Range high</span><input type="number" min="0" value={profile.revenue_high ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_high:numberValue(event.target.value) }))} /></label>
          <label><span>Currency</span><input value={profile.revenue_currency} onChange={event => setProfile(value => ({ ...value, revenue_currency:event.target.value.toUpperCase().slice(0, 3) }))} /></label>
          <label><span>Year</span><input type="number" min="1900" max="2100" value={profile.revenue_year ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_year:numberValue(event.target.value) }))} /></label>
          <label><span>Confidence</span><select value={profile.revenue_confidence} onChange={event => setProfile(value => ({ ...value, revenue_confidence:event.target.value as CompanyAdminProfilePatch['revenue_confidence'] }))}><option value="unknown">Unknown</option><option value="confirmed">Confirmed</option><option value="strong">Strong</option><option value="verify">Verify</option></select></label>
          <label><span>Source</span><input value={profile.revenue_source_name ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_source_name:event.target.value }))} /></label>
          <label className="wide"><span>Source URL</span><input type="url" value={profile.revenue_source_url ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_source_url:event.target.value }))} /></label>
        </div>
      </section>

      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Relationship &amp; follow-up</strong><span>Internal CRM state</span></div>
        <div className="company-admin-form-grid">
          <label><span>Status</span><select value={profile.relationship_status} onChange={event => setProfile(value => ({ ...value, relationship_status:event.target.value as CompanyRelationshipStatus }))}>{relationshipStatuses.map(status => <option key={status} value={status}>{relationshipLabel(status)}</option>)}</select></label>
          <label><span>Account owner</span><input value={profile.account_owner ?? ''} onChange={event => setProfile(value => ({ ...value, account_owner:event.target.value }))} /></label>
          <label><span>Last contacted</span><input type="datetime-local" value={localDateTime(profile.last_contacted_at)} onChange={event => setProfile(value => ({ ...value, last_contacted_at:event.target.value ? new Date(event.target.value).toISOString() : null }))} /></label>
          <label><span>Next action</span><input type="date" value={profile.next_action_date ?? ''} onChange={event => setProfile(value => ({ ...value, next_action_date:event.target.value }))} /></label>
          <label className="wide"><span>Internal summary</span><textarea rows={4} value={profile.internal_summary ?? ''} onChange={event => setProfile(value => ({ ...value, internal_summary:event.target.value }))} /></label>
        </div>
      </section>

      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Contacts</strong><span>{contacts.length} saved</span></div>
        <div className="company-admin-inline-form">
          <input aria-label="Contact name" value={contactName} onChange={event => setContactName(event.target.value)} placeholder="Name" />
          <input aria-label="Contact title" value={contactTitle} onChange={event => setContactTitle(event.target.value)} placeholder="Title" />
          <input aria-label="Contact email" type="email" value={contactEmail} onChange={event => setContactEmail(event.target.value)} placeholder="Email" />
          <input aria-label="Contact phone" value={contactPhone} onChange={event => setContactPhone(event.target.value)} placeholder="Phone" />
          <input aria-label="Contact LinkedIn" type="url" value={contactLinkedin} onChange={event => setContactLinkedin(event.target.value)} placeholder="LinkedIn URL" />
          <button onClick={addContact} disabled={busy || !contactName.trim()}>Add contact</button>
        </div>
        <div className="company-admin-inline-form">
          <input aria-label="Contact source name" value={contactSourceName} onChange={event => setContactSourceName(event.target.value)} placeholder="Source name" />
          <input aria-label="Contact source URL" type="url" value={contactSourceUrl} onChange={event => setContactSourceUrl(event.target.value)} placeholder="Source URL" />
          <input aria-label="Contact verified at" type="datetime-local" value={contactVerifiedAt} onChange={event => setContactVerifiedAt(event.target.value)} />
        </div>
        <div className="company-admin-list">{contacts.length ? contacts.map(contact => <div key={contact.contact_id}><strong>{contact.name}</strong><span>{[contact.title, contact.email, contact.phone].filter(Boolean).join(' · ') || 'No contact detail'}</span>{contact.linkedin_url && <a href={contact.linkedin_url} target="_blank" rel="noreferrer">LinkedIn ↗</a>}{contact.source_name && <small>{contact.source_name}{contact.verified_at ? ' · verified ' + new Date(contact.verified_at).toLocaleDateString() : ''}</small>}<button type="button" onClick={() => setEditingContact({ ...contact })}>Edit contact</button></div>) : <span className="company-admin-empty">No private contacts recorded.</span>}</div>
        {editingContact && <div className="company-admin-contact-editor">
          <div className="company-admin-card-heading"><strong>Edit contact</strong><span>{editingContact.name}</span></div>
          <div className="company-admin-inline-form">
            <input aria-label="Edit contact name" value={editingContact.name} onChange={event => setEditingContact(value => value ? ({ ...value, name:event.target.value }) : value)} placeholder="Name" />
            <input aria-label="Edit contact title" value={editingContact.title ?? ''} onChange={event => setEditingContact(value => value ? ({ ...value, title:event.target.value }) : value)} placeholder="Title" />
            <input aria-label="Edit contact email" type="email" value={editingContact.email ?? ''} onChange={event => setEditingContact(value => value ? ({ ...value, email:event.target.value }) : value)} placeholder="Email" />
            <input aria-label="Edit contact phone" value={editingContact.phone ?? ''} onChange={event => setEditingContact(value => value ? ({ ...value, phone:event.target.value }) : value)} placeholder="Phone" />
            <input aria-label="Edit contact LinkedIn" type="url" value={editingContact.linkedin_url ?? ''} onChange={event => setEditingContact(value => value ? ({ ...value, linkedin_url:event.target.value }) : value)} placeholder="LinkedIn URL" />
          </div>
          <div className="company-admin-inline-form">
            <input aria-label="Edit contact source name" value={editingContact.source_name ?? ''} onChange={event => setEditingContact(value => value ? ({ ...value, source_name:event.target.value }) : value)} placeholder="Source name" />
            <input aria-label="Edit contact source URL" type="url" value={editingContact.source_url ?? ''} onChange={event => setEditingContact(value => value ? ({ ...value, source_url:event.target.value }) : value)} placeholder="Source URL" />
            <input aria-label="Edit contact verified at" type="datetime-local" value={localDateTime(editingContact.verified_at)} onChange={event => setEditingContact(value => value ? ({ ...value, verified_at:event.target.value ? new Date(event.target.value).toISOString() : null }) : value)} />
            <label><input aria-label="Contact active" type="checkbox" checked={editingContact.active} onChange={event => setEditingContact(value => value ? ({ ...value, active:event.target.checked }) : value)} /> Active</label>
            <button type="button" onClick={() => void saveContact()} disabled={busy || !editingContact.name.trim()}>Save contact</button>
            <button type="button" onClick={() => setEditingContact(null)} disabled={busy}>Cancel</button>
          </div>
        </div>}
      </section>

      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Contact / activity history</strong><span>{activities.length} logged interactions</span></div>
        <div className="company-admin-inline-form activity-form">
          <select aria-label="Activity type" value={activityType} onChange={event => setActivityType(event.target.value)}><option value="email">Email</option><option value="call">Call</option><option value="meeting">Meeting</option><option value="linkedin">LinkedIn</option><option value="other">Other</option></select>
          <input aria-label="Activity date" type="datetime-local" value={activityDate} onChange={event => setActivityDate(event.target.value)} />
          <select aria-label="Activity contact" value={activityContactId} onChange={event => setActivityContactId(event.target.value)}><option value="">No specific contact</option>{contacts.filter(contact => contact.active).map(contact => <option key={contact.contact_id} value={contact.contact_id}>{contact.name}</option>)}</select>
          <input aria-label="Activity subject" value={activitySubject} onChange={event => setActivitySubject(event.target.value)} placeholder="Subject / purpose" />
          <input aria-label="Activity outcome" value={activityOutcome} onChange={event => setActivityOutcome(event.target.value)} placeholder="Outcome" />
          <input aria-label="Activity next action" type="date" value={activityNextAction} onChange={event => setActivityNextAction(event.target.value)} />
          <textarea aria-label="Activity details" rows={2} value={activityDetails} onChange={event => setActivityDetails(event.target.value)} placeholder="What happened?" />
          <button onClick={addActivity} disabled={busy || !activityDate}>Log interaction</button>
        </div>
        <div className="company-admin-timeline">{activities.length ? activities.map(activity => <article key={activity.activity_id}><time>{new Date(activity.occurred_at).toLocaleString()}</time><strong>{relationshipLabel(activity.activity_type)}</strong>{activity.contact_id && <span>Contact: {contactById.get(activity.contact_id)?.name ?? activity.contact_id}</span>}{activity.subject && <span>{activity.subject}</span>}{activity.outcome && <span>{activity.outcome}</span>}{activity.details && <p>{activity.details}</p>}{activity.next_action_date && <small>Next action {activity.next_action_date}</small>}</article>) : <span className="company-admin-empty">No outreach or interaction history recorded.</span>}</div>
      </section>

      <section className="company-admin-card company-admin-notes-card">
        <div className="company-admin-card-heading"><strong>Internal notes</strong><span>{notes.length} notes · private</span></div>
        <div className="company-admin-new-note"><textarea aria-label="New company note" rows={3} value={newNote} onChange={event => setNewNote(event.target.value)} placeholder="Add research, relationship, ownership or sales context…" /><button onClick={addNote} disabled={busy || !newNote.trim()}>Add note</button></div>
        <div className="company-admin-notes">{notes.length ? notes.map(note => <article key={note.note_id}><textarea aria-label={`Edit note ${note.note_id}`} rows={3} value={noteDrafts[note.note_id] ?? note.note} onChange={event => setNoteDrafts(value => ({ ...value, [note.note_id]:event.target.value }))} /><div><small>{note.updated_at ? new Date(note.updated_at).toLocaleString() : 'Saved note'}</small><button onClick={() => saveNote(note.note_id)} disabled={busy || !(noteDrafts[note.note_id] ?? '').trim()}>Save note</button></div></article>) : <span className="company-admin-empty">No private notes recorded.</span>}</div>
      </section>
    </div>
  </section>
}
