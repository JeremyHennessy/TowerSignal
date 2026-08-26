import type { NysChangesPayload, NysSystem } from '../types/nys'

export function NysChangesView({ payload }: { payload: NysChangesPayload; systems: NysSystem[]; onSelect: (row: NysSystem | null) => void }) {
  return <section className="changes-view" aria-label="TowerSignal NYS changes"><div className="change-count">{payload.events.length.toLocaleString()} retained NYS changes</div></section>
}
