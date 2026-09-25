import { useMemo, useState } from 'react'
import { captureCompanyExternalActivity } from '../companyAdmin/client'
import { parseExternalActivityFile } from '../companyAdmin/externalCapture'
import type { CompanyAdminContact, CompanyExternalActivityCapture } from '../types/companyAdmin'

function human(value:string):string{
  return value.replaceAll('-',' ').replaceAll('_',' ').replace(/(^|\s)\S/g,match=>match.toUpperCase())
}

export function CompanyExternalActivityCapturePanel({
  companyId,
  contacts,
  onCaptured,
}:{
  companyId:string
  contacts:CompanyAdminContact[]
  onCaptured:()=>Promise<void>
}) {
  const [parsed,setParsed]=useState<CompanyExternalActivityCapture|null>(null)
  const [filename,setFilename]=useState('')
  const [contactId,setContactId]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const [message,setMessage]=useState<string|null>(null)

  const activeContacts=useMemo(()=>contacts.filter(contact=>contact.active),[contacts])

  const readFile=async(file:File)=>{
    setError(null);setMessage(null)
    try{
      const raw=await file.text()
      const next=parseExternalActivityFile(file.name,raw)
      const enriched={
        ...next,
        external_metadata:{...next.external_metadata,file_name:file.name},
      }
      setParsed(enriched)
      setFilename(file.name)
      const participantSet=new Set(next.participant_emails.map(email=>email.toLowerCase()))
      const matches=activeContacts.filter(contact=>contact.email&&participantSet.has(contact.email.toLowerCase()))
      setContactId(matches.length===1?matches[0].contact_id:'')
    }catch(err){
      setParsed(null);setFilename('');setContactId('')
      setError(err instanceof Error?err.message:'Unable to parse external activity file')
    }
  }

  const capture=async()=>{
    if(!parsed)return
    setBusy(true);setError(null);setMessage(null)
    try{
      const result=await captureCompanyExternalActivity(companyId,{
        ...parsed,
        contact_id:contactId||null,
      })
      if(result.created){
        setMessage('Interaction imported into the authoritative activity history.')
        await onCaptured()
      }else{
        setMessage('This external interaction was already captured; no duplicate was created.')
      }
    }catch(err){
      setError(err instanceof Error?err.message:'Unable to capture external activity')
    }finally{
      setBusy(false)
    }
  }

  return <section className="company-external-capture" aria-label="Email and calendar capture">
    <div className="company-admin-card-heading">
      <div><strong>Email &amp; calendar capture</strong><span>Import exported .eml or .ics metadata into the activity timeline</span></div>
      <small>No OAuth tokens or email message bodies are stored</small>
    </div>
    <div className="company-external-capture-input">
      <label>
        <span>Choose exported message or calendar event</span>
        <input
          aria-label="External activity file"
          type="file"
          accept=".eml,.ics,message/rfc822,text/calendar"
          onChange={event=>{
            const file=event.target.files?.[0]
            if(file) void readFile(file)
          }}
        />
      </label>
    </div>

    {error&&<div className="company-admin-error"><strong>Capture error.</strong><span>{error}</span></div>}
    {message&&<div className="company-external-capture-message">{message}</div>}

    {parsed&&<div className="company-external-capture-preview">
      <div>
        <small>{human(parsed.external_source)} · {filename}</small>
        <strong>{parsed.subject||'Untitled interaction'}</strong>
        <span>{new Date(parsed.occurred_at).toLocaleString()} · {human(parsed.activity_type)}</span>
      </div>
      <div>
        <small>Participants</small>
        <span>{parsed.participant_emails.length?parsed.participant_emails.join(' · '):'No participant emails found'}</span>
      </div>
      {parsed.details&&<p>{parsed.details}</p>}
      <label>
        <span>Link to contact</span>
        <select aria-label="Captured activity contact" value={contactId} onChange={event=>setContactId(event.target.value)}>
          <option value="">No specific contact</option>
          {activeContacts.map(contact=><option key={contact.contact_id} value={contact.contact_id}>{contact.name}{contact.email?' · '+contact.email:''}</option>)}
        </select>
      </label>
      <button type="button" onClick={()=>void capture()} disabled={busy}>
        {busy?'Importing…':'Import interaction'}
      </button>
    </div>}
  </section>
}
