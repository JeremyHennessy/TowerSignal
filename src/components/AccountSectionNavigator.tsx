import { useEffect, useState } from 'react'

type AccountSectionTarget = {
  label: string
  selector?: string
  heading?: string
}

const targets: AccountSectionTarget[] = [
  { label: 'Overview', selector: '.account-profile-page .detail-header' },
  { label: 'Workflow', selector: '.account-profile-page .workflow-account-section' },
  { label: 'Sales brief', selector: '.account-profile-page .sales-precall-pack' },
  { label: 'Field pack', selector: '.account-profile-page .technician-field-pack' },
  { label: 'Tower location', selector: '.account-profile-page section.planimetric-section' },
  { label: 'Domestic water', selector: '.account-profile-page section.domestic-water-section' },
  { label: 'Property & contacts', heading: 'Building context' },
  { label: 'Current signals', heading: 'Current TowerSignal signals' },
  { label: 'Samples', heading: 'Sample history' },
  { label: 'Inspections', heading: 'NYC Health inspection history' },
  { label: 'OATH', heading: 'OATH case lifecycle' },
  { label: 'Sources', heading: 'Source & provenance' },
]

function findTarget(target: AccountSectionTarget): HTMLElement | null {
  if (target.selector) return document.querySelector<HTMLElement>(target.selector)
  if (!target.heading) return null
  const headings = document.querySelectorAll<HTMLElement>('.account-profile-page .detail-panel h3')
  const heading = [...headings].find(item => item.textContent?.trim() === target.heading)
  return heading?.closest<HTMLElement>('section') ?? null
}

export function AccountSectionNavigator() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const go = (target: AccountSectionTarget) => {
    findTarget(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setOpen(false)
  }

  const buttons = targets.map(target => <button type="button" key={target.label} onClick={() => go(target)}>{target.label}</button>)

  return <>
    <aside className="account-section-rail" aria-label="On this account">
      <span>On this account</span>
      <nav>{buttons}</nav>
    </aside>
    <div className={`account-jump-control ${open ? 'open' : ''}`}>
      <button type="button" className="account-jump-trigger" aria-expanded={open} aria-controls="account-jump-menu" onClick={() => setOpen(value => !value)}>
        Jump to <span aria-hidden="true">⌄</span>
      </button>
      {open && <div id="account-jump-menu" className="account-jump-menu" role="menu" aria-label="Jump to account section">{buttons}</div>}
    </div>
  </>
}
