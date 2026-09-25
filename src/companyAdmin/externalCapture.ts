import type { CompanyExternalActivityCapture } from '../types/companyAdmin'

function unfoldLines(value:string):string[]{
  return value.replace(/\r\n/g,'\n').replace(/\n[ \t]/g,'').split('\n')
}

function emailsFrom(values:string[]):string[]{
  const result=new Set<string>()
  for(const value of values){
    for(const match of value.matchAll(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi)){
      result.add(match[0].toLowerCase())
    }
  }
  return [...result]
}

function decodeIcsText(value:string):string{
  return value
    .replace(/\\n/gi,'\n')
    .replace(/\\,/g,',')
    .replace(/\\;/g,';')
    .replace(/\\\\/g,'\\')
    .trim()
}

function isoFromIcsDate(value:string):string{
  const clean=value.trim()
  let match=clean.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/)
  if(match){
    const [,year,month,day,hour,minute,second]=match
    return new Date(Date.UTC(+year,+month-1,+day,+hour,+minute,+second)).toISOString()
  }
  match=clean.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$/)
  if(match){
    const [,year,month,day,hour,minute,second]=match
    return new Date(+year,+month-1,+day,+hour,+minute,+second).toISOString()
  }
  match=clean.match(/^(\d{4})(\d{2})(\d{2})$/)
  if(match){
    const [,year,month,day]=match
    return new Date(Date.UTC(+year,+month-1,+day)).toISOString()
  }
  const parsed=new Date(clean)
  if(Number.isNaN(parsed.getTime())) throw new Error('Calendar event has an unsupported DTSTART')
  return parsed.toISOString()
}

function first(values:Map<string,string[]>,key:string):string|null{
  return values.get(key)?.[0]??null
}

export function parseEmlActivity(raw:string):CompanyExternalActivityCapture{
  const normalized=raw.replace(/\r\n/g,'\n')
  const headerEnd=normalized.indexOf('\n\n')
  if(headerEnd<0) throw new Error('Email file does not contain RFC-style headers')
  const headerLines=unfoldLines(normalized.slice(0,headerEnd))
  const headers=new Map<string,string[]>()
  for(const line of headerLines){
    const colon=line.indexOf(':')
    if(colon<=0) continue
    const key=line.slice(0,colon).trim().toLowerCase()
    const value=line.slice(colon+1).trim()
    const list=headers.get(key)??[]
    list.push(value)
    headers.set(key,list)
  }

  const messageId=headers.get('message-id')?.[0]?.replace(/^<|>$/g,'').trim()
  if(!messageId) throw new Error('Email file is missing Message-ID; cannot deduplicate safely')
  const dateValue=headers.get('date')?.[0]
  if(!dateValue) throw new Error('Email file is missing Date')
  const occurred=new Date(dateValue)
  if(Number.isNaN(occurred.getTime())) throw new Error('Email Date could not be parsed')

  const from=headers.get('from')??[]
  const to=headers.get('to')??[]
  const cc=headers.get('cc')??[]
  const participants=emailsFrom([...from,...to,...cc])
  const detailParts=[
    from.length?'From: '+from.join(', '):null,
    to.length?'To: '+to.join(', '):null,
    cc.length?'Cc: '+cc.join(', '):null,
  ].filter((value):value is string=>Boolean(value))

  return {
    activity_type:'email',
    occurred_at:occurred.toISOString(),
    contact_id:null,
    subject:headers.get('subject')?.[0]?.trim()||null,
    details:detailParts.join('\n')||null,
    outcome:null,
    next_action_date:null,
    external_source:'eml',
    external_event_id:messageId,
    external_url:null,
    external_direction:'unknown',
    participant_emails:participants,
    external_metadata:{
      from,
      to,
      cc,
      reply_to:headers.get('reply-to')??[],
    },
  }
}

export function parseIcsActivity(raw:string):CompanyExternalActivityCapture{
  const lines=unfoldLines(raw)
  const start=lines.findIndex(line=>line.trim().toUpperCase()==='BEGIN:VEVENT')
  const end=start>=0?lines.findIndex((line,index)=>index>start&&line.trim().toUpperCase()==='END:VEVENT'):-1
  if(start<0||end<0) throw new Error('Calendar file does not contain a VEVENT')

  const values=new Map<string,string[]>()
  for(const line of lines.slice(start+1,end)){
    const colon=line.indexOf(':')
    if(colon<=0) continue
    const property=line.slice(0,colon)
    const key=property.split(';')[0].trim().toUpperCase()
    const value=line.slice(colon+1).trim()
    const list=values.get(key)??[]
    list.push(value)
    values.set(key,list)
  }

  const uid=first(values,'UID')
  if(!uid) throw new Error('Calendar event is missing UID; cannot deduplicate safely')
  const dtStart=first(values,'DTSTART')
  if(!dtStart) throw new Error('Calendar event is missing DTSTART')
  const organizer=values.get('ORGANIZER')??[]
  const attendees=values.get('ATTENDEE')??[]
  const participantEmails=emailsFrom([...organizer,...attendees])
  const location=first(values,'LOCATION')
  const endValue=first(values,'DTEND')
  const url=first(values,'URL')

  return {
    activity_type:'meeting',
    occurred_at:isoFromIcsDate(dtStart),
    contact_id:null,
    subject:first(values,'SUMMARY')?decodeIcsText(first(values,'SUMMARY') as string):null,
    details:location?'Location: '+decodeIcsText(location):null,
    outcome:null,
    next_action_date:null,
    external_source:'ics',
    external_event_id:uid.trim(),
    external_url:url||null,
    external_direction:'unknown',
    participant_emails:participantEmails,
    external_metadata:{
      organizer,
      attendees,
      location:location?decodeIcsText(location):null,
      end_at:endValue?isoFromIcsDate(endValue):null,
    },
  }
}

export function parseExternalActivityFile(filename:string,raw:string):CompanyExternalActivityCapture{
  const lower=filename.toLowerCase()
  if(lower.endsWith('.eml')) return parseEmlActivity(raw)
  if(lower.endsWith('.ics')) return parseIcsActivity(raw)
  throw new Error('Only .eml and .ics files are supported')
}
