import { useEffect, useMemo, useState } from 'react'
import {
  addCompanyActivity,
  addCompanyContact,
  addCompanyNote,
  loadCompanyAdminAccess,
  loadCompanyAdminSnapshot,
  saveCompanyAdminProfile,
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
    website: null,
    headquarters_address: null,
    headquarters_city: null,
    headquarters_region: null,
    headquarters_postal_code: null,
    headquarters_country: null,
    parent_company_id: null,
    parent_company_name: null,
    company_type: null,
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
  const [activityType, setActivityType] = useState('email')
  const [activityDate, setActivityDate] = useState(() => localDateTime(new Date().toISOString()))
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

  const locationSummary = useMemo(() => [
    profile.headquarters_city,
    profile.headquarters_region,
    profile.headquarters_country,
  ].filter(Boolean).join(', ') || 'Not recorded', [profile.headquarters_city, profile.headquarters_region, profile.headquarters_country])

  const saveProfile = async () => {
    setBusy(true)
    setError(null)
    try {
      const saved = await saveCompanyAdminProfile(companyId, canonicalName, profile)
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
      const savedProfile = await saveCompanyAdminProfile(companyId, canonicalName, profile)
      setProfile(patchFrom(savedProfile))
      await addCompanyContact(companyId, {
        name: contactName.trim(),
        title: text(contactTitle),
        email: text(contactEmail),
        phone: text(contactPhone),
        linkedin_url: null,
        notes: null,
        active: true,
      })
      setContactName('')
      setContactTitle('')
      setContactEmail('')
      setContactPhone('')
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to add contact')
    } finally {
      setBusy(false)
    }
  }

  const addActivity = async () => {
    if (!activityDate) return
    setBusy(true)
    setError(null)
    try {
      await saveCompanyAdminProfile(companyId, canonicalName, profile)
      const occurredAt = new Date(activityDate).toISOString()
      await addCompanyActivity(companyId, {
        activity_type: activityType,
        occurred_at: occurredAt,
        contact_id: null,
        subject: null,
        details: text(activityDetails),
        outcome: text(activityOutcome),
        next_action_date: text(activityNextAction),
      })
      const nextProfile = {
        ...profile,
        relationship_status: profile.relationship_status === 'uncontacted' ? 'contacted' as const : profile.relationship_status,
        last_contacted_at: occurredAt,
        next_action_date: text(activityNextAction) ?? profile.next_action_date,
      }
      await saveCompanyAdminProfile(companyId, canonicalName, nextProfile)
      setProfile(nextProfile)
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
      const savedProfile = await saveCompanyAdminProfile(companyId, canonicalName, profile)
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
          <label><span>Legal name</span><input value={profile.legal_name ?? ''} onChange={event => setProfile(value => ({ ...value, legal_name:text(event.target.value) }))} /></label>
          <label><span>Rolled-up normalized name</span><input value={profile.rollup_name ?? ''} onChange={event => setProfile(value => ({ ...value, rollup_name:text(event.target.value) }))} /></label>
          <label><span>Rollup company ID</span><input value={profile.rollup_company_id ?? ''} onChange={event => setProfile(value => ({ ...value, rollup_company_id:text(event.target.value) }))} placeholder="Explicit only; never inferred" /></label>
          <label><span>Website</span><input type="url" value={profile.website ?? ''} onChange={event => setProfile(value => ({ ...value, website:text(event.target.value) }))} placeholder="https://…" /></label>
          <label><span>Company type</span><input value={profile.company_type ?? ''} onChange={event => setProfile(value => ({ ...value, company_type:text(event.target.value) }))} /></label>
          <label><span>Parent company</span><input value={profile.parent_company_name ?? ''} onChange={event => setProfile(value => ({ ...value, parent_company_name:text(event.target.value) }))} /></label>
          <label><span>Parent company ID</span><input value={profile.parent_company_id ?? ''} onChange={event => setProfile(value => ({ ...value, parent_company_id:text(event.target.value) }))} /></label>
        </div>
        <div className="company-admin-form-grid address-grid">
          <label className="wide"><span>HQ street address</span><input value={profile.headquarters_address ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_address:text(event.target.value) }))} /></label>
          <label><span>City</span><input value={profile.headquarters_city ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_city:text(event.target.value) }))} /></label>
          <label><span>State / region</span><input value={profile.headquarters_region ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_region:text(event.target.value) }))} /></label>
          <label><span>Postal code</span><input value={profile.headquarters_postal_code ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_postal_code:text(event.target.value) }))} /></label>
          <label><span>Country</span><input value={profile.headquarters_country ?? ''} onChange={event => setProfile(value => ({ ...value, headquarters_country:text(event.target.value) }))} /></label>
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
          <label><span>Source</span><input value={profile.revenue_source_name ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_source_name:text(event.target.value) }))} /></label>
          <label className="wide"><span>Source URL</span><input type="url" value={profile.revenue_source_url ?? ''} onChange={event => setProfile(value => ({ ...value, revenue_source_url:text(event.target.value) }))} /></label>
        </div>
      </section>

      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Relationship &amp; follow-up</strong><span>Internal CRM state</span></div>
        <div className="company-admin-form-grid">
          <label><span>Status</span><select value={profile.relationship_status} onChange={event => setProfile(value => ({ ...value, relationship_status:event.target.value as CompanyRelationshipStatus }))}>{relationshipStatuses.map(status => <option key={status} value={status}>{relationshipLabel(status)}</option>)}</select></label>
          <label><span>Account owner</span><input value={profile.account_owner ?? ''} onChange={event => setProfile(value => ({ ...value, account_owner:text(event.target.value) }))} /></label>
          <label><span>Last contacted</span><input type="datetime-local" value={localDateTime(profile.last_contacted_at)} onChange={event => setProfile(value => ({ ...value, last_contacted_at:event.target.value ? new Date(event.target.value).toISOString() : null }))} /></label>
          <label><span>Next action</span><input type="date" value={profile.next_action_date ?? ''} onChange={event => setProfile(value => ({ ...value, next_action_date:text(event.target.value) }))} /></label>
          <label className="wide"><span>Internal summary</span><textarea rows={4} value={profile.internal_summary ?? ''} onChange={event => setProfile(value => ({ ...value, internal_summary:text(event.target.value) }))} /></label>
        </div>
      </section>

      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Contacts</strong><span>{contacts.length} saved</span></div>
        <div className="company-admin-inline-form">
          <input aria-label="Contact name" value={contactName} onChange={event => setContactName(event.target.value)} placeholder="Name" />
          <input aria-label="Contact title" value={contactTitle} onChange={event => setContactTitle(event.target.value)} placeholder="Title" />
          <input aria-label="Contact email" type="email" value={contactEmail} onChange={event => setContactEmail(event.target.value)} placeholder="Email" />
          <input aria-label="Contact phone" value={contactPhone} onChange={event => setContactPhone(event.target.value)} placeholder="Phone" />
          <button onClick={addContact} disabled={busy || !contactName.trim()}>Add contact</button>
        </div>
        <div className="company-admin-list">{contacts.length ? contacts.map(contact => <div key={contact.contact_id}><strong>{contact.name}</strong><span>{[contact.title, contact.email, contact.phone].filter(Boolean).join(' · ') || 'No contact detail'}</span></div>) : <span className="company-admin-empty">No private contacts recorded.</span>}</div>
      </section>

      <section className="company-admin-card">
        <div className="company-admin-card-heading"><strong>Contact / activity history</strong><span>{activities.length} logged interactions</span></div>
        <div className="company-admin-inline-form activity-form">
          <select aria-label="Activity type" value={activityType} onChange={event => setActivityType(event.target.value)}><option value="email">Email</option><option value="call">Call</option><option value="meeting">Meeting</option><option value="linkedin">LinkedIn</option><option value="other">Other</option></select>
          <input aria-label="Activity date" type="datetime-local" value={activityDate} onChange={event => setActivityDate(event.target.value)} />
          <input aria-label="Activity outcome" value={activityOutcome} onChange={event => setActivityOutcome(event.target.value)} placeholder="Outcome" />
          <input aria-label="Activity next action" type="date" value={activityNextAction} onChange={event => setActivityNextAction(event.target.value)} />
          <textarea aria-label="Activity details" rows={2} value={activityDetails} onChange={event => setActivityDetails(event.target.value)} placeholder="What happened?" />
          <button onClick={addActivity} disabled={busy || !activityDate}>Log interaction</button>
        </div>
        <div className="company-admin-timeline">{activities.length ? activities.map(activity => <article key={activity.activity_id}><time>{new Date(activity.occurred_at).toLocaleString()}</time><strong>{relationshipLabel(activity.activity_type)}</strong>{activity.outcome && <span>{activity.outcome}</span>}{activity.details && <p>{activity.details}</p>}{activity.next_action_date && <small>Next action {activity.next_action_date}</small>}</article>) : <span className="company-admin-empty">No outreach or interaction history recorded.</span>}</div>
      </section>

      <section className="company-admin-card company-admin-notes-card">
        <div className="company-admin-card-heading"><strong>Internal notes</strong><span>{notes.length} notes · private</span></div>
        <div className="company-admin-new-note"><textarea aria-label="New company note" rows={3} value={newNote} onChange={event => setNewNote(event.target.value)} placeholder="Add research, relationship, ownership or sales context…" /><button onClick={addNote} disabled={busy || !newNote.trim()}>Add note</button></div>
        <div className="company-admin-notes">{notes.length ? notes.map(note => <article key={note.note_id}><textarea aria-label={`Edit note ${note.note_id}`} rows={3} value={noteDrafts[note.note_id] ?? note.note} onChange={event => setNoteDrafts(value => ({ ...value, [note.note_id]:event.target.value }))} /><div><small>{note.updated_at ? new Date(note.updated_at).toLocaleString() : 'Saved note'}</small><button onClick={() => saveNote(note.note_id)} disabled={busy || !(noteDrafts[note.note_id] ?? '').trim()}>Save note</button></div></article>) : <span className="company-admin-empty">No private notes recorded.</span>}</div>
      </section>
    </div>
  </section>
}
