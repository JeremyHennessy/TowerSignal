import { useMemo, type ReactNode } from 'react'
import qrcode from 'qrcode-generator'
import type { ChangeEvent } from '../types/history'
import type { Metadata, SystemDetail, SystemSummary } from '../types/data'
import { reportDate, reportGeometry, reportModel, reportMoney, reportName, reportNumber } from '../utils/accountReportModel'

const tabs = ['Summary', 'Evidence', 'Next steps', 'Sources']
const sourceSpecs = [
  ['Cooling-tower register', 'Registered unit, active listing and sample dates.', 'y4fw-iqfr'],
  ['NYC Health inspection results', 'Findings, inspection notes and summons numbers.', 'f9wb-g8mb'],
  ['OATH hearing and case status', 'Decisions, dismissals and the published penalty balance.', 'jz4z-kudi'],
  ['PLUTO property data', 'Floors, residential units, building area and year built.', '64uk-42ks'],
  ['Housing registration and contacts', 'Recorded corporate owner and agent.', 'tesw-yqqr', 'feu5-w2e2'],
  ['NYC building footprints', 'Published building outline, matched by building ID.', '5zhs-2jue'],
  ['NYC cooling-tower mapping', 'Mapped rooftop feature; imagery year is 2022.', 'x748-37q7'],
]
const ref = (n: string) => <sup>{n.split(' ').map((i, k) => <a key={k} href={`#tsr-source-${i}`}>[{i}] </a>)}</sup>
const time = (v?: string | null) => v && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) ? `${v.slice(11, 16)} UTC` : 'Not shown'
const safeUrl = (v?: string) => v && /^https:\/\//i.test(v) ? v : undefined

function Qr({ url }: { url: string }) {
  const qr = useMemo(() => { const value = qrcode(0, 'M'); value.addData(url, 'Byte'); value.make(); return value }, [url])
  const count = qr.getModuleCount()
  const path = Array.from({ length: count }, (_, r) => Array.from({ length: count }, (_, c) => qr.isDark(r, c) ? `M${c + 2},${r + 2}h1v1h-1z` : '').join('')).join('')
  return <svg viewBox={`0 0 ${count + 4} ${count + 4}`} role="img" aria-label="Open this account" shapeRendering="crispEdges"><rect width="100%" height="100%" fill="white" /><path d={path} fill="#0d2348" /></svg>
}

export function ClientSiteReport({ row, detail, metadata }: { row: SystemSummary; detail: SystemDetail; metadata: Metadata; historyEvents: ChangeEvent[] }) {
  // The Account loader clears its previous detail in an effect after a route change.
  // Never render stale account evidence or throw during that loading frame.
  if (row.system_id !== detail.identity.system_id) return null
  const m = reportModel(row, detail, metadata)
  const shape = reportGeometry(detail)
  const applicationSha = /^[a-f0-9]{40}$/.test(import.meta.env.VITE_REPORT_APPLICATION_SHA || '') ? import.meta.env.VITE_REPORT_APPLICATION_SHA : null
  const accountUrl = `https://jeremyhennessy.github.io/TowerSignal/#/account/${encodeURIComponent(row.system_id)}`
  const page = (index: number, subtitle: string, children: ReactNode) => <section className={`tsr-page tsr-page-${index + 1}`} id={`tsr-page-${index + 1}`} key={index}>
    <header className="tsr-header"><img src={`${import.meta.env.BASE_URL}marketing/towersignal-logo.webp`} alt="TowerSignal" /><div><b>ACCOUNT REPORT</b><span>{subtitle}</span></div></header>
    <nav className="tsr-nav">{tabs.map((tab, i) => <a href={`#tsr-page-${i + 1}`} key={tab} className={i === index ? 'active' : ''}>{`0${i + 1}`} &nbsp; {tab}</a>)}</nav>
    {children}
    <footer className="tsr-footer"><span><b>TowerSignal</b> &nbsp;·&nbsp; {m.address} &nbsp;·&nbsp; System {row.system_id}</span><span>ACCOUNT EXPORT &nbsp; / &nbsp; 0{index + 1} OF 04</span></footer>
  </section>
  const title = (kicker: string, heading: string, text: string) => <div className="tsr-heading"><p className="tsr-kicker">{kicker}</p><h1>{heading}</h1><p>{text}</p></div>
  const active = detail.inspection_history.find(i => i.status)?.status
  const firstDate = m.previous || m.latest
  const source = (id: string) => detail.metadata.sources.find(s => s.dataset_id === id)
  return <article className="client-pdf-report" aria-label="Client-ready site intelligence report" data-report-design="approved-20260922" data-report-system={row.system_id} data-report-app-sha={applicationSha || "not-published"}>
    {page(0, reportDate(m.snapshot, 'long'), <>
      <div className="tsr-hero"><div className="tsr-rings" /><p className="tsr-kicker">COOLING-TOWER ACCOUNT REPORT</p><h1>{m.address}</h1><p>{reportName(row.borough)}, New York {row.zip}</p><div className="tsr-hero-meta"><span>System <b>{row.system_id}</b></span><span>Data snapshot <b>{reportDate(m.snapshot)}</b></span><b>Account export</b></div></div>
      <div className="tsr-summary"><h2>{m.latest ? 'Ask for the latest test records.' : 'Ask for the missing test records.'}<br />{m.penaltyLine}</h2><p>The public records point to two follow-ups. They do not tell us whether the water is safe.</p></div>
      <div className="tsr-stats">
        <div><strong>{reportNumber(row.active_equipment)}</strong><b>Registered cooling unit{row.active_equipment === 1 ? '' : 's'} {ref('1')}</b><p>{active === 'Active' ? 'Listed as active in the register' : 'Confirm current operating status'}</p></div>
        <div className="warm"><strong>{m.age == null ? 'Not shown' : m.age} {m.age != null && <small>days</small>}</strong><b>{m.latest ? 'Since the latest listed sample' : 'No public sample date'} {ref('1')}</b><p>{m.latest ? `Latest date shown: ${reportDate(m.latest)}` : 'Ask for the latest testing records'}</p></div>
        <div className="warm"><strong>{reportMoney(m.balance)}</strong><b>{m.balanceComplete ? 'Penalty balance shown' : 'Known case balance'} {ref('3')}</b><p>{m.unpaid.length === 1 ? `One ${m.month} case · Amount in US dollars` : m.balance == null ? 'No exact-ticket balance available' : `${m.cases.length} latest-inspection findings · US dollars`}</p></div>
      </div>
      <section className="tsr-matters"><h3>What matters</h3>
        <div className="tsr-finding"><span className="tsr-badge verify">VERIFY</span><div><h4>{m.latest ? 'There may be newer test records.' : 'No public Legionella sample date is shown.'} {ref('1')}</h4><p>{m.latest ? `The register lists ${reportDate(m.latest, 'long').replace(/ \d{4}$/, '')} as the latest sample date. Ask for newer records before deciding that a test was missed.` : 'Ask for the sample dates and laboratory reports. Missing public dates do not prove that testing did not occur.'}</p></div></div>
        <div className="tsr-finding"><span className="tsr-badge recorded">RECORDED</span><div><h4>{m.decisionTitle} {ref('2 3')}</h4><p>{m.decisionText}</p></div></div>
        <div className="tsr-finding"><span className="tsr-badge unknown">NOT SHOWN</span><div><h4>A sample date is not a test result. {ref('1')}</h4><p>The supplied sample-date record does not show a laboratory result. This report does not establish contamination or an all-clear.</p></div></div>
      </section>
      <aside className="tsr-priority"><strong>{row.priority_score} <small>/ 100</small></strong><div><b>TowerSignal follow-up priority</b><p>Helps decide what to check first. It is not a health or safety score. {m.scoreCopy}</p></div></aside>
    </>)}
    {page(1, 'Evidence, not assumptions', <>
      {title('READ THE EVIDENCE', 'What the records actually say', 'A test date, an inspection finding and a hearing decision answer different questions.')}
      <section className="tsr-samples"><div className="tsr-section-title"><h3>Water-testing dates {ref('1')}</h3><span>{m.dates.length} date{m.dates.length === 1 ? '' : 's'} in the supplied register record</span></div>
        <div className="tsr-timeline">
          <div><label>{m.dates.length > 2 ? 'PREVIOUS DATE SHOWN' : 'FIRST DATE SHOWN'}</label><i /><b>{reportDate(firstDate)}</b><span>{firstDate ? 'Sample date listed' : 'No public date available'}</span></div>
          <div><label>{m.interval == null ? 'LATEST AVAILABLE DATE' : `${m.interval} DAYS AFTER THE ${m.previous ? new Intl.DateTimeFormat('en', { month: 'long', timeZone: 'UTC' }).format(new Date(m.previous + 'T12:00:00Z')).toUpperCase() : 'PRIOR'} DATE`}</label><i /><b>{reportDate(m.latest)}</b><span>Latest sample date listed</span></div>
          <div><label>{m.age == null ? 'AGE CANNOT BE CALCULATED' : `${m.age} DAYS AFTER THE ${m.latest ? new Intl.DateTimeFormat('en', { month: 'long', timeZone: 'UTC' }).format(new Date(m.latest + 'T12:00:00Z')).toUpperCase() : 'LATEST'} DATE`}</label><i /><b>{reportDate(m.snapshot)}</b><span>This report’s data snapshot</span></div>
        </div>
        <div className="tsr-note"><b>What to check:</b> Is there a newer sample, what did the laboratory find, and was the system operating? {m.dates.length === 2 ? 'Two listed dates do not prove they were the only samples taken.' : 'The listed dates do not prove they were the only samples taken.'}</div>
      </section>
      <section className="tsr-cases"><h3>{m.month || 'Inspection'} findings and later case outcomes {ref('2 3')}</h3><p className="tsr-case-intro">NYC Health inspection: <b>{reportDate(m.inspection?.inspection_date, 'long')}.</b> Hearing outcomes below are matched by exact ticket number.{m.cases.length > 3 ? ` Showing 3 of ${m.cases.length} findings; all records are in the account.` : ''}</p>
        <div className="tsr-case-table"><div className="tsr-case-head"><b>What the inspector recorded</b><b>What the later case record shows</b></div>
          {m.cases.slice(0, 3).map((c, i) => <div className="tsr-case-row" key={i}><div><h4>{c.title}</h4><p>{c.text}</p><small>{c.violation.violation_code || 'Code not shown'} · Ticket {c.violation.summons_number || 'not shown'}</small></div><div><span className={`tsr-badge ${c.dismissed ? 'dismissed' : c.outcome ? 'verify' : 'unknown'}`}>{c.outcome?.hearing_result?.toUpperCase() || 'NOT SHOWN'}</span><h4>{c.outcome?.balance_due == null ? 'Balance not shown' : `${reportMoney(c.outcome.balance_due)} balance shown`}</h4><p>Decision: {reportDate(c.outcome?.decision_date)}</p><p>{c.dismissed ? (m.dismissalExcluded ? 'Excluded from the findings score' : 'Dismissal shown in the case record') : c.outcome?.compliance_status ? `Published status: ${c.outcome.compliance_status}` : 'Verify the current case record'}</p></div></div>)}
          {!m.cases.length && <div className="tsr-case-empty"><h4>{m.inspection ? 'No findings in the latest joined inspection.' : 'No inspection record is available in this snapshot.'}</h4><p>Neither statement establishes today’s water quality. Earlier records and any newer evidence should be reviewed in the account.</p></div>}
        </div>
      </section>
      <div className="tsr-note warm tsr-separate"><b>Keep the two checks separate.</b> A case outcome does not show today’s water quality. A payment does not, by itself, prove that the underlying issue was corrected.</div>
    </>)}
    {page(2, 'Site context and action plan', <>
      {title('TURN THE EVIDENCE INTO A NEXT STEP', 'The site. The people. The next steps.', 'Use the right building record and ask for the documents that fill the gaps.')}
      <section className="tsr-context"><figure className="tsr-map">{shape ? <svg viewBox="0 0 280 230" role="img" aria-label="Published building outline and mapped cooling-tower features"><defs><pattern id={`tsr-grid-${row.system_id}`} width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#eaf0f8" strokeWidth=".7" /></pattern></defs><rect width="280" height="230" fill={`url(#tsr-grid-${row.system_id})`} /><path d={shape.buildingPath} fill="#dbe6f4" stroke="#527193" strokeWidth="1.5" fillRule="evenodd" /><path d={shape.towerPath} fill="#ff6a13" stroke="#a74612" strokeWidth="1" />{shape.marker && <><circle cx={shape.marker[0]} cy={shape.marker[1]} r="11" fill="none" stroke="#ff6a13" strokeWidth="1.5" /><path d={`M${shape.marker[0] + 11} ${shape.marker[1]}H246`} fill="none" stroke="#ff6a13" /><rect x="213" y={shape.marker[1] - 23} width="47" height="20" rx="2" fill="white" /><text x="236.5" y={shape.marker[1] - 9} textAnchor="middle" fill="#a74612" fontSize="10" fontWeight="700">TOWER</text></>}<path d="M244 38V18M239 25L244 18L249 25" fill="none" stroke="#0d2348" strokeWidth="1.5" /><text x="244" y="13" textAnchor="middle" fontSize="9" fill="#5f6f85">N</text><text x="14" y="216" fontSize="9" fill="#5f6f85">Building outline + mapped feature · Not a survey</text></svg> : <div className="tsr-map-missing">No exact building geometry is shown.<br />Confirm the site layout directly.</div>}<figcaption><b>{shape?.towerCount ? `${shape.towerCount} mapped cooling-tower feature${shape.towerCount === 1 ? '' : 's'}` : 'No mapped cooling-tower feature shown'}</b>{shape?.imageryYear ? ` from ${shape.imageryYear} imagery.` : '.'} Matched to this building, not proof of today’s equipment layout. {ref('6 7')}</figcaption></figure>
        <div className="tsr-building"><h3>Building snapshot {ref('4')}</h3><div className="tsr-building-stats"><div><b>{reportNumber(detail.building_context?.floors)}</b><span>floors</span></div><div><b>{reportNumber(detail.building_context?.residential_units)}</b><span>residential units</span></div><div><b>{detail.building_context?.year_built || 'Not shown'}</b><span>year built</span></div></div><p className="tsr-area">Published building area: <b>{reportNumber(detail.building_context?.building_area_sqft)}{detail.building_context?.building_area_sqft == null ? '' : ' sq ft'}</b></p><label>{m.ownerFromHpd ? 'OWNER LISTED IN HOUSING REGISTRATION' : 'OWNER LISTED IN PLUTO'} {ref(m.ownerFromHpd ? '5' : '4')}</label><h4>{m.owner}</h4><label>AGENT LISTED IN HOUSING REGISTRATION {ref('5')}</label><h4>{m.agent}</h4><p>Last registration shown: {reportDate(detail.hpd_registration?.last_registration_date)}.<br />Confirm the current contact before outreach.</p><p className="tsr-owner-note">{m.plutoOwner === 'Not shown' && m.ownerFromHpd ? 'The separate PLUTO owner field is unavailable; the owner above comes from housing registration.' : 'Public ownership and agent records do not establish who currently procures cooling-tower services.'}</p></div>
      </section>
      <div className="tsr-identity"><span><b>System:</b> {row.system_id}</span><span><b>Building ID (BIN):</b> {detail.identity.bin || 'Not shown'}</span><span><b>Tax lot (BBL):</b> {detail.identity.bbl || 'Not shown'}</span></div>
      <section className="tsr-actions"><h3>Three simple next steps</h3>{[
        ['ASK THE BUILDING MANAGER', 'Send the newest water-test reports.', 'Request the sample dates, laboratory results and the periods when the cooling system was operating.', 'Complete when the records identify this system and show the dates and results.'],
        ['ASK THE PERSON HANDLING THE CASE', m.unpaid.length === 1 ? `Confirm the status of ticket ${m.unpaid[0].ticket_number}.` : 'Confirm the latest inspection and case status.', 'Check the current balance and any payment receipt. Separately, ask for records showing how the cited issue was addressed.', 'Complete when both the case status and the corrective-action record are checked.'],
        ['FOR THE REPORT REVIEWER', 'Update the account with what is confirmed.', 'Add the new evidence and current contact. Leave unanswered questions marked “Verify” and set the next review date.', 'Complete when each update has a supporting document or source and a date.'],
      ].map((action, i) => <div className="tsr-action" key={i}><b className="tsr-step">{i + 1}</b><div><label>{action[0]}</label><h4>{action[1]}</h4><p>{action[2]}</p><small><i className="tsr-checkbox" />{action[3]}</small></div></div>)}</section>
    </>)}
    {page(3, 'Sources and reading guide', <>
      {title('FOLLOW THE FACTS BACK TO THE SOURCE', 'Every key fact has a source.', 'Click a source name to open the official dataset.')}
      <p className="tsr-retrieval">Retrieved <b>{reportDate(source('y4fw-iqfr')?.retrieved_at)}</b> (UTC). Dataset updates may be newer than individual building records.</p>
      <table className="tsr-sources"><thead><tr><th>NO.</th><th>SOURCE AND WHAT IT SUPPORTS</th><th>SOURCE UPDATED</th></tr></thead><tbody>{sourceSpecs.map(([name, description, ...ids], i) => <tr key={name} id={`tsr-source-${i + 1}`}><td>{`0${i + 1}`}</td><td><a href={safeUrl(source(ids[0])?.url) || `https://data.cityofnewyork.us/d/${ids[0]}`}>{name}</a><p>{i === 1 && m.month ? `${m.month} findings, inspection notes and summons numbers.` : description} &nbsp; {ids.map((id, j) => <span key={id}>{j > 0 && ' + '}<a href={safeUrl(source(id)?.url) || `https://data.cityofnewyork.us/d/${id}`}>{id}</a></span>)}</p></td><td>{reportDate(source(ids[0])?.source_last_updated_at)}<small>{source(ids[0]) ? `Retrieved ${time(source(ids[0])?.retrieved_at)}` : 'Not in this snapshot'}</small></td></tr>)}</tbody></table>
      <aside className="tsr-return"><div><h4>Return to the full account</h4><p>Snapshot: {reportDate(m.snapshot)} · Priority model: {detail.scoring?.priority_model_version || 'Not shown'}</p><p>Published application: {applicationSha ? applicationSha.slice(0, 12) : 'Not shown'}{applicationSha && <> · <a href={`https://github.com/JeremyHennessy/TowerSignal/commit/${applicationSha}`}>Release record</a></>}</p><a className="tsr-account-link" href={accountUrl}>Open {m.address} in TowerSignal →</a></div><a className="tsr-qr" href={accountUrl}><Qr url={accountUrl} /><span>OPEN ACCOUNT</span></a></aside>
      <section className="tsr-guide"><h4>How to read this report</h4><p><b>Recorded:</b> a public source says it. <b>Verify:</b> ask for current proof. <b>Not shown:</b> the available record does not answer the question.</p><p>Records are matched by system ID, exact ticket number, building ID, tax lot or housing registration—not by a similar name.</p><h4>What this report does not establish</h4><p>This report uses the published account snapshot, not a new inspection. It does not establish water safety, current operation, completed repairs or compliance. Verify current conditions and case status before relying on it.</p></section>
    </>)}
  </article>
}
