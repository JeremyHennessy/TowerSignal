import { useEffect, useRef, useState } from 'react'
import { AccountEvidenceWorkspace } from './AccountEvidenceWorkspace'

type AccountMode = 'summary' | 'sales' | 'field' | 'evidence' | 'history'
type AccountModeGroup = AccountMode | 'legacy-evidence'

const modes: Array<{ value: AccountMode; label: string; detail: string }> = [
  { value: 'summary', label: 'Summary', detail: 'Decision, workflow and priority evidence' },
  { value: 'sales', label: 'Sales', detail: 'Pre-call brief and qualification prompts' },
  { value: 'field', label: 'Field', detail: 'Dispatch, roof geometry and water assets' },
  { value: 'evidence', label: 'Evidence', detail: 'Grouped source records and observed relationships' },
  { value: 'history', label: 'History', detail: 'Unified and source-specific chronology' },
]

const summaryHeadings = new Set(['Current TowerSignal signals', 'Why this score', 'Official Legionella building evidence'])
const historyHeadings = new Set([
  'Historical profile',
  'Sample history',
  'NYC Health inspection history',
  'OATH case lifecycle',
  'TowerSignal History',
  'ACRIS property activity',
  'Historical water context',
])

function classify(element: HTMLElement): AccountModeGroup | null {
  if (element.classList.contains('account-mode-tabs')) return null
  if (element.classList.contains('account-evidence-workspace')) return 'evidence'
  if (element.classList.contains('account-decision-summary') || element.classList.contains('workflow-account-section')) return 'summary'
  if (element.classList.contains('sales-precall-pack')) return 'sales'
  if (element.classList.contains('technician-field-pack') || element.classList.contains('planimetric-section') || element.classList.contains('domestic-water-section')) return 'field'
  if (element.classList.contains('account-unified-timeline')) return 'history'
  const heading = element.querySelector('h3')?.textContent?.trim() ?? ''
  if (summaryHeadings.has(heading)) return 'summary'
  if (historyHeadings.has(heading)) return 'history'
  if (element.tagName === 'SECTION' || element.tagName === 'DETAILS') return 'legacy-evidence'
  return null
}

export function AccountModeTabs() {
  const [mode, setMode] = useState<AccountMode>('summary')
  const rootRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const tabs = rootRef.current
    const panel = tabs?.closest('.detail-panel') as HTMLElement | null
    if (!panel) return

    const apply = () => {
      Array.from(panel.children).forEach(child => {
        if (!(child instanceof HTMLElement)) return
        const group = classify(child)
        if (!group) return
        child.dataset.accountModeGroup = group
        child.hidden = group === 'legacy-evidence' ? true : group !== mode
      })
      window.dispatchEvent(new CustomEvent('towersignal:account-mode-change', { detail: { mode } }))
    }

    apply()
    const observer = new MutationObserver(apply)
    observer.observe(panel, { childList: true })
    return () => {
      observer.disconnect()
      Array.from(panel.querySelectorAll<HTMLElement>('[data-account-mode-group]')).forEach(element => { element.hidden = false })
    }
  }, [mode])

  return <>
    <nav ref={rootRef} className="account-mode-tabs" aria-label="Account profile modes">
      {modes.map(item => <button type="button" key={item.value} className={mode === item.value ? 'active' : ''} aria-pressed={mode === item.value} onClick={() => setMode(item.value)}><strong>{item.label}</strong><span>{item.detail}</span></button>)}
    </nav>
    {mode === 'evidence' && <AccountEvidenceWorkspace />}
  </>
}
