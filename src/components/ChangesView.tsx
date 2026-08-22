import type { ChangesPayload } from '../types/history'

export function ChangesView({ payload }: { payload: ChangesPayload; onSelectSystem: (systemId: string) => void }) {
  return <section className="changes-view" aria-label="TowerSignal changes">
    <h2>What changed?</h2>
    <p>Diagnostic render only.</p>
    <span>{payload.events.length.toLocaleString()} retained events loaded</span>
  </section>
}
