import type { SystemDetail } from '../types/data'

export function InstitutionalFacilitySection({ detail }: { detail: SystemDetail }) {
  const context = detail.cms_institutional_context
  if (!context?.facilities.length) return null
  return <section className="property-context-section institutional-facility-section">
    <h3>Institutional facility context</h3>
    <div className="property-coverage-callout">
      <strong>CMS facility identity matched to this exact NYC property</strong>
      <p>Facility type, ownership and chain are account-qualification context only. They do not establish cooling-tower status, current condition, service responsibility, or an incumbent contractor.</p>
    </div>
    <div className="signal-list">{context.facilities.map(facility => <article className="signal-card" key={`${facility.source_dataset_id}-${facility.source_facility_id}`}>
      <div className="signal-card-head"><strong>{facility.facility_name ?? facility.facility_type ?? 'CMS institutional facility'}</strong><span>{facility.source_kind === 'HOSPITAL' ? 'Hospital' : 'Nursing home'}</span></div>
      <dl className="identity-grid">
        <div><dt>CMS facility ID</dt><dd>{facility.source_facility_id}</dd></div>
        <div><dt>Facility type</dt><dd>{facility.facility_type ?? '—'}</dd></div>
        <div><dt>Ownership</dt><dd>{facility.ownership_type ?? '—'}</dd></div>
        <div><dt>Chain</dt><dd>{facility.chain_name ?? '—'}</dd></div>
        <div><dt>Exact BBL</dt><dd>{facility.bbl}</dd></div>
        <div><dt>PAD BIN</dt><dd>{facility.bin ?? '—'}</dd></div>
      </dl>
    </article>)}</div>
    <p className="microcopy">{context.evidence_boundaries.property_link} {context.evidence_boundaries.facility} {context.evidence_boundaries.non_tower} {context.evidence_boundaries.provider}</p>
  </section>
}
