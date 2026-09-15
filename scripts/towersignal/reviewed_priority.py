"""Priority 1.1: auditable research timing rules, not a calibrated risk/purchase probability."""
from __future__ import annotations
from datetime import date
from typing import Any

MODEL = '1.1'
CONTEXT_NOTE = ('HPD housing violations, SWO dispositions, facade filings, domestic-water records, 311 complaints, '
                'CMS facilities, lead lines, distribution-water samples, property transactions, contacts and procurement '
                'remain contextual evidence. They do not establish a cooling-tower fault. General news and neighborhood '
                'proximity do not add points. Payment is not proof of physical remediation.')

def age(as_of: date, value: Any) -> int | None:
    try:
        result = (as_of - date.fromisoformat(str(value)[:10])).days
        return result if result >= 0 else None
    except (ValueError, TypeError):
        return None

def score(detail: dict[str, Any], row: dict[str, Any], links: list[dict[str, Any]], as_of: date) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    notes: list[str] = []
    def component(points: int, reason: str, source: str, source_date: str | None = None) -> dict[str, Any]:
        return {'points': points, 'reason': reason, 'source': source, 'source_date': source_date}
    dismissed = {str(c['ticket_number']) for c in detail.get('oath_case_history', [])
                 if c.get('hearing_result') == 'DISMISSED' and age(as_of, c.get('decision_date')) is not None}
    findings = []
    excluded = 0
    for inspection in detail.get('inspection_history', []):
        days = age(as_of, inspection.get('inspection_date'))
        if days is None or days > 365:
            continue
        violations = []
        for violation in inspection.get('violations', []):
            if violation.get('summons_number') and str(violation['summons_number']) in dismissed:
                excluded += 1
            else:
                violations.append(violation)
        if not violations:
            continue
        factor = 1 if days <= 90 else .6 if days <= 180 else .3
        severe = any(str(v.get('violation_type') or '').strip().upper() in {'CRITICAL', 'PHH', 'PUBLIC HEALTH HAZARD'} for v in violations)
        points = round((40 + (10 if severe else 0)) * factor)
        findings.append(component(points, f'NYC Health findings on {inspection["inspection_date"]} ({days} days ago; '
                                  f'{len(violations)} non-dismissed citation records; ' + ('critical / public health hazard' if severe else 'general') +
                                  f'; recency factor {factor:g}). A recorded finding is not proof it remains uncorrected.',
                                  'NYC cooling-tower inspection / exact summons OATH status', inspection['inspection_date']))
    finding = max(findings, key=lambda c: (c['points'], c['source_date']), default=None)
    notices = []
    for link in links:
        days = age(as_of, link.get('event_date') or link.get('source_date'))
        if link.get('episode_status') == 'CLOSED' or link.get('scope') != 'BUILDING_LEVEL' or days is None:
            continue
        if link.get('result') not in {'PCR_POSITIVE_REMEDIATION_ORDER', 'CULTURE_POSITIVE'} or days > 90:
            continue
        points = 70 if days <= 14 else 45 if days <= 30 else 20
        notices.append(component(points, f'Officially named building: {link["result"].replace("_", " ").lower()} '
                                  f'({link.get("event_date") or link["source_date"]}; {days} days ago). Completion is not established by this record; '
                                  'verify follow-up. Building-level match, not identification of an individual source tower.', link['source_url'], link.get('event_date') or link['source_date']))
    notice = max(notices, key=lambda c: (c['points'], c['source_date']), default=None)
    # Public-health reporting and inspection citations may describe the same episode. Do not add both.
    strongest = max([c for c in (finding, notice) if c], key=lambda c: c['points'], default=None)
    if strongest:
        components.append(strongest)
    if finding and notice:
        notes.append('The higher of inspection findings and named-building public-health follow-up is used; overlapping evidence is not added twice.')
    if excluded:
        notes.append(f'{excluded} recent citation record(s) excluded after an exact-ticket published dismissal. Other citations remain independently eligible.')
    samples = age(as_of, row.get('latest_sample_date'))
    if not row.get('latest_sample_date'):
        components.append(component(18, 'No usable public sample date; verify operating and sampling status. Absence of a public date is not a violation.', 'NYC tower registration'))
    elif samples is None:
        notes.append('Future or invalid public sample date: no gap points; source date requires review.')
    elif samples > 36:
        points = 30 if samples > 60 else 25 if samples > 45 else 20
        components.append(component(points, f'Public sampling follow-up: {samples} days since {row["latest_sample_date"]}; '
                                    'beyond 31 days plus the 5-day reporting allowance. Operating status remains unverified.', 'NYC tower registration', row['latest_sample_date']))
    elif samples > 31:
        notes.append('Latest public sample is 32–36 days old: within the five-day reporting allowance, so no sampling-gap score yet.')
    if not finding and not notice:
        latest = max((i.get('inspection_date') or '' for i in detail.get('inspection_history', [])), default='')
        days = age(as_of, latest)
        if days is not None and days <= 90:
            components.append(component(10, f'Recent NYC Health inspection ({latest}); regulatory activity only, not an adverse finding.', 'NYC tower inspections', latest))
    else:
        notes.append('No separate inspection-activity bonus: the inspection is already represented in the findings component.')
    projects = []
    for job in detail.get('dob_activity_history', []):
        if not job.get('explicit_cooling_tower_mention'):
            continue
        status = str(job.get('filing_status') or '').lower()
        if job.get('signoff_date') or any(s in status for s in ('signed off', 'sign-off', 'withdrawn', 'cancelled', 'disapproved')):
            continue
        dates = [str(job.get(k)) for k in ('filing_date', 'approved_date', 'first_permit_date', 'current_status_date')
                 if age(as_of, job.get(k)) is not None and age(as_of, job.get(k)) <= 90]
        if dates:
            projects.append((max(dates), str(job.get('job_filing_number') or 'filing')))
    if projects:
        latest, job = max(projects)
        components.append(component(15, f'Explicit cooling-tower work in DOB NOW {job}; published lifecycle activity {latest}. '
                                    'Not signed off in the supplied filing; verify procurement/service opportunity.', 'DOB NOW exact BBL', latest))
    equipment = max(0, int(row.get('active_equipment') or 0))
    if equipment > 1:
        components.append(component(min(18, (equipment - 1) * 6), f'{equipment} active registered units: commercial account scale only, capped at 18 points.', 'NYC tower registry'))
    total = sum(c['points'] for c in components)
    remaining = 100
    for c in components:
        requested = c['points']
        c['points'] = min(remaining, requested)
        remaining -= c['points']
        if requested != c['points']:
            c['reason'] += f' ({requested} before the overall 100-point cap.)'
    return {'score': 100 - remaining, 'components': [c for c in components if c['points']], 'priority_model_version': MODEL,
            'as_of': as_of.isoformat(), 'uncapped_score': total, 'notes': notes,
            'context_note': CONTEXT_NOTE, 'validation_status': 'RULE_BASED_NOT_PREDICTIVELY_CALIBRATED',
            'official_building_followup': bool(notice),
            'review_basis': 'Source-event recency, PHH severity, exact-ticket dismissals, reporting allowance and non-duplicated named-building evidence.'}
