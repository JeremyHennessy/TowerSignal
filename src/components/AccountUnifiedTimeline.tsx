import { useMemo, useState } from 'react'
import type { ChangeEvent } from '../types/history'
import type { SystemDetail } from '../types/data'
import type { AcrisPropertyActivity } from '../types/acris'
import { formatDate, formatTimestamp } from '../domain/labels'

type TimelineCategory = 'compliance' | 'sampling' | 'projects' | 'ownership' | 'towersignal'

type TimelineItem = {
  key: string
  date: string
  category: TimelineCategory
  title: string
  detail: string
  source: string
  detected?: boolean
}

const categoryLabels: Record<TimelineCategory, string> = {
  compliance: 'Compliance',
  sampling: 'Sampling',
  projects: 'Projects',
  ownership: 'Ownership',
  towersignal: 'TowerSignal',
}

function eventLabel(value: string) {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function itemTime(value: string) {
  const time = new Date(value).getTime()
  return Number.isFinite(time) ? time : 0
}

export function AccountUnifiedTimeline({ detail, historyEvents }: { detail: SystemDetail; historyEvents: ChangeEvent[] }) {
  const [filter, setFilter] = useState<'all' | TimelineCategory>('all')
  const [expanded, setExpanded] = useState(false)

  const items = useMemo(() => {
    const next: TimelineItem[] = []

    detail.sample_history.dates.forEach((date, index) => next.push({
      key: `sample-${date}-${index}`,
      date,
      category: 'sampling',
      title: 'Public sample date',
      detail: 'Published cooling-tower sample history date.',
      source: 'NYC cooling-tower registration',
    }))

    detail.inspection_history.forEach((inspection, index) => {
      if (!inspection.inspection_date) return
      next.push({
        key: `inspection-${inspection.inspection_date}-${index}`,
        date: inspection.inspection_date,
        category: 'compliance',
        title: `NYC Health inspection · ${inspection.inspection_type}`,
        detail: `${inspection.violation_count.toLocaleString()} published violation${inspection.violation_count === 1 ? '' : 's'}`,
        source: 'NYC Health inspection history',
      })
    })

    ;(detail.oath_case_history ?? []).forEach((oathCase, index) => {
      const date = oathCase.decision_date ?? oathCase.hearing_date ?? oathCase.violation_date
      if (!date) return
      next.push({
        key: `oath-${oathCase.ticket_number}-${index}`,
        date,
        category: 'compliance',
        title: `OATH ticket ${oathCase.ticket_number}`,
        detail: [oathCase.hearing_status, oathCase.hearing_result, oathCase.compliance_status].filter(Boolean).join(' · ') || 'Published OATH lifecycle event',
        source: 'OATH exact summons match',
      })
    })

    ;(detail.dob_activity_history ?? []).forEach((job, index) => {
      const date = job.activity_date ?? job.current_status_date ?? job.filing_date
      if (!date) return
      next.push({
        key: `dob-${job.job_filing_number ?? index}-${date}`,
        date,
        category: 'projects',
        title: `DOB ${job.job_filing_number ?? 'filing'} · ${job.job_type ?? 'project activity'}`,
        detail: job.job_description ?? job.filing_status ?? 'Exact-BBL DOB project activity',
        source: 'DOB NOW exact BBL',
      })
    })

    const acris = (detail as SystemDetail & { acris_activity?: AcrisPropertyActivity | null }).acris_activity
    acris?.documents.forEach((document, index) => {
      const date = document.recorded_date ?? document.document_date
      if (!date) return
      next.push({
        key: `acris-${document.document_id}-${index}`,
        date,
        category: 'ownership',
        title: `ACRIS ${document.doc_type ?? 'recorded document'}`,
        detail: document.document_id,
        source: 'ACRIS exact BBL/document ID',
      })
    })

    historyEvents.forEach((event, index) => next.push({
      key: `history-${event.detected_at}-${event.event_type}-${index}`,
      date: event.detected_at,
      category: 'towersignal',
      title: eventLabel(event.event_type),
      detail: event.source_observation_date ? `Source observation ${formatDate(event.source_observation_date)}` : 'Snapshot change first observed by TowerSignal',
      source: `${event.source} · ${event.evidence_basis}`,
      detected: true,
    }))

    return next.sort((a, b) => itemTime(b.date) - itemTime(a.date))
  }, [detail, historyEvents])

  const matching = filter === 'all' ? items : items.filter(item => item.category === filter)
  const visible = expanded ? matching : matching.slice(0, 18)

  return <section className="account-unified-timeline" aria-labelledby="account-activity-title">
    <div className="account-timeline-head">
      <div><span className="page-kicker">Unified history</span><h3 id="account-activity-title">Account activity timeline</h3><p>Sampling, compliance, project, recorded-property and TowerSignal detection events in one chronology. Detection dates remain distinct from underlying source-event dates.</p></div>
      <strong>{matching.length.toLocaleString()} events</strong>
    </div>
    <div className="account-timeline-filters" aria-label="Timeline filters">
      <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>All</button>
      {(Object.keys(categoryLabels) as TimelineCategory[]).map(category => <button key={category} className={filter === category ? 'active' : ''} onClick={() => setFilter(category)}>{categoryLabels[category]}</button>)}
    </div>
    {visible.length === 0 ? <div className="empty-inline">No events match this timeline filter.</div> : <ol className="account-timeline-list">{visible.map(item => <li key={item.key} className={`timeline-${item.category}`}><time>{item.detected ? formatTimestamp(item.date) : formatDate(item.date)}</time><div><span>{categoryLabels[item.category]}</span><strong>{item.title}</strong><p>{item.detail}</p><small>{item.source}</small></div></li>)}</ol>}
    {matching.length > 18 && <button type="button" className="account-timeline-more" onClick={() => setExpanded(value => !value)}>{expanded ? 'Show recent 18' : `Show all ${matching.length.toLocaleString()} events`}</button>}
  </section>
}
