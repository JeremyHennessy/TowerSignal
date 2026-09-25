import { useEffect, useMemo, useState } from 'react'
import type { CompanyAdminProfile, CompanySalesAccount, CompanySalesAccountMember } from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'
import { useAdminNavigation } from '../companyAdmin/navigation'
import { buildCompanyDirectory } from '../companyAdmin/directory'
import { loadCompanyEvidence } from '../companyAdmin/client'
import type { CompanyEvidence } from '../companyAdmin/evidence'

const number=new Intl.NumberFormat('en-US')
const pageSize=50
export function AdminFirmDirectory({firms,profiles,accounts,members}: {
  firms:KnownFirmSummaryRecord[];profiles:CompanyAdminProfile[];accounts:CompanySalesAccount[];members:CompanySalesAccountMember[]
}) {
  const [evidence,setEvidence]=useState<CompanyEvidence|null>(null)
  const [error,setError]=useState<string|null>(null)
  const navigation=useAdminNavigation()
  const query=navigation.params.get('q')??''
  const scope=navigation.choice('coverage',['all','mapped','unmapped','parent'] as const,'all')
  const view=navigation.choice('hierarchy',['companies','parents'] as const,'companies')
  const requestedPage=Number(navigation.params.get('page')??1)
  const page=Number.isSafeInteger(requestedPage)&&requestedPage>0?requestedPage-1:0
  const setPage=(next:number)=>navigation.update({page:String(next+1)})
  useEffect(()=>{let cancelled=false;void loadCompanyEvidence().then(value=>{if(!cancelled)setEvidence(value)}).catch(err=>{if(!cancelled)setError(err instanceof Error?err.message:'Parent evidence could not load')});return()=>{cancelled=true}},[])
  const rows=useMemo(()=>buildCompanyDirectory(firms,profiles,accounts,members,evidence),[firms,profiles,accounts,members,evidence])
  const filtered=useMemo(()=>{
    const needle=query.trim().toLowerCase()
    return rows.filter(row=>(scope==='all'||(scope==='mapped'?Boolean(row.account):scope==='unmapped'?!row.account:row.parents.length>0))&&(!needle||[row.name,...row.parents.map(parent=>parent.name),...row.identities.flatMap(identity=>[identity.name,identity.normalized??''])].join(' ').toLowerCase().includes(needle)))
  },[rows,query,scope])
  const parentGroups=useMemo(()=>{
    const groups=new Map<string,{name:string;rows:typeof rows}>()
    for(const row of filtered)for(const parent of row.parents){const group=groups.get(parent.name)??{name:parent.name,rows:[]};if(!group.rows.includes(row))group.rows.push(row);groups.set(parent.name,group)}
    return [...groups.values()].sort((a,b)=>a.name.localeCompare(b.name))
  },[filtered])
  const visiblePage=Math.min(page,Math.max(0,Math.ceil(filtered.length/pageSize)-1))
  const mappedIdentityCount=rows.filter(row=>row.account).reduce((sum,row)=>sum+row.identities.length,0)
  return <div className="admin-all-firms">
    <div className="admin-company-card-heading"><div><strong>All firms &amp; company roll-ups</strong><span>{number.format(firms.length)} public firm identities · {number.format(accounts.length)} CRM master companies · {number.format(mappedIdentityCount)} mapped identities</span></div></div>
    <p className="admin-directory-note">Reviewed aliases are grouped under their master company. Every remaining firm is listed separately. Normalized names support search; they do not establish a company or parent match.</p>
    {error&&<div role="alert" className="company-admin-error">Additional parent evidence could not load: {error}. Recorded CRM parents are shown; confirmed-link coverage is unavailable.</div>}
    <div className="admin-directory-controls">
      <label>Find a company<input aria-label="Search all firms" value={query} placeholder="Company, source name, normalized name or parent…" onChange={event=>{navigation.update({q:event.target.value,page:null},true)}}/></label>
      <label>Coverage<select aria-label="Firm mapping coverage" value={scope} onChange={event=>{navigation.update({coverage:event.target.value,page:null})}}><option value="all">All firms</option><option value="mapped">Mapped to CRM</option><option value="unmapped">Not yet mapped</option><option value="parent">Parent recorded</option></select></label>
      <div className="admin-account-views" role="group" aria-label="Firm hierarchy view"><a href={navigation.href({hierarchy:'companies'})} aria-current={view==='companies'?'page':undefined}>Company table</a><a href={navigation.href({hierarchy:'parents'})} aria-current={view==='parents'?'page':undefined}>Parent groups</a></div>
    </div>
    {view==='companies'?<>
      <div className="admin-directory-pagination"><span>{number.format(filtered.length)} company rows · {number.format(filtered.reduce((sum,row)=>sum+row.identities.length,0))} retained identities</span><div><button disabled={visiblePage===0} onClick={()=>setPage(visiblePage-1)}>Previous</button><span>Page {visiblePage+1} of {Math.max(1,Math.ceil(filtered.length/pageSize))}</span><button disabled={(visiblePage+1)*pageSize>=filtered.length} onClick={()=>setPage(visiblePage+1)}>Next</button></div></div>
      <div className="table-scroll"><table className="account-table admin-all-firms-table"><thead><tr><th>Company / master name</th><th>Normalized names &amp; source identities</th><th>Parent / ownership</th><th>Mapping</th><th>Public evidence</th></tr></thead><tbody>
        {filtered.slice(visiblePage*pageSize,(visiblePage+1)*pageSize).map(row=><tr key={row.id}>
          <td><a className="table-link" href={row.account?`#/admin-company/${encodeURIComponent(row.id)}`:`#/company/${encodeURIComponent(row.id)}`}><strong>{row.name}</strong></a><small>{row.account?'Open CRM account':'Open source firm'}</small></td>
          <td><span>{[...new Set(row.identities.map(identity=>identity.normalized).filter(Boolean))].slice(0,2).join(' · ')||'Normalized name not recorded'}</span><details><summary>{number.format(row.identities.length)} source {row.identities.length===1?'identity':'identities'}</summary><ul className="admin-identity-list">{row.identities.map(identity=><li key={identity.id}>{identity.firm?<a href={`#/company/${encodeURIComponent(identity.id)}`}>{identity.name}</a>:<span>{identity.name}</span>}<small>Normalized: {identity.normalized||'Not recorded'}</small></li>)}</ul></details></td>
          <td>{row.parents.length?row.parents.map(parent=><div key={parent.name+parent.status}><strong>{parent.name}</strong><small>{parent.status}{parent.source&&<> · <a href={parent.source} target="_blank" rel="noreferrer">Evidence ↗</a></>}</small></div>):<span>Not established</span>}</td>
          <td><span className="admin-status-chip">{row.account?'Reviewed CRM mapping':'Not yet mapped'}</span><small>{row.account?row.account.account_classification.replaceAll('-',' '):'Source identity retained'}</small></td>
          <td><strong>{number.format(row.observations)} observations</strong><small>{[...new Set(row.identities.flatMap(identity=>identity.firm?.roles??[]))].map(role=>role.replaceAll('_',' ').toLowerCase()).join(' · ')}</small></td>
        </tr>)}
        {!filtered.length&&<tr><td colSpan={5}>No companies match these filters. Clear the search or choose All firms.</td></tr>}
      </tbody></table></div>
    </>:<div className="table-scroll"><table className="account-table admin-all-firms-table"><thead><tr><th>Parent / group</th><th>Operating companies</th><th>Retained identities</th><th>Ownership evidence</th></tr></thead><tbody>
      {parentGroups.map(group=><tr key={group.name}><td><strong>{group.name}</strong><small>{group.rows.length} master {group.rows.length===1?'company':'companies'}</small></td><td>{group.rows.map(row=><div key={row.id}><a href={`#/admin-company/${encodeURIComponent(row.id)}`}>{row.name}</a><small>{row.identities.map(identity=>identity.name).join(' · ')}</small></div>)}</td><td>{number.format(group.rows.reduce((sum,row)=>sum+row.identities.length,0))}</td><td>{group.rows.map(row=>row.parents.filter(parent=>parent.name===group.name).map(parent=><div key={row.id+parent.status}>{parent.source?<a href={parent.source} target="_blank" rel="noreferrer">{row.name} evidence ↗</a>:'Source not recorded'}<small>{parent.status}</small></div>))}</td></tr>)}
      {!parentGroups.length&&<tr><td colSpan={4}>No parent relationships are recorded for this selection. This does not establish independent ownership.</td></tr>}
    </tbody></table></div>}
  </div>
}
