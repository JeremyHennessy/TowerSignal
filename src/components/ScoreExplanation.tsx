import type { SystemDetail } from '../types/data'
import { formatDate } from '../domain/labels'

type ReviewedScoring = SystemDetail['scoring'] & { as_of?: string; notes?: string[]; context_note?: string; uncapped_score?: number }
export function ScoreExplanation({ scoring }: { scoring: ReviewedScoring }) {
  return <section className="reviewed-score" aria-label="Priority score explanation"><h3>Why this score</h3>
    {scoring.components.length ? <ul className="score-list">{scoring.components.map((component, index) => <li key={`${component.reason}-${index}`}><strong>+{component.points}</strong><span>{component.reason}</span></li>)}</ul> : <div className="empty-inline">No priority points were assigned. This does not certify safety or compliance.</div>}
    <p className="microcopy"><strong>{scoring.score} / 100</strong> · Research priority model {scoring.priority_model_version}{scoring.as_of ? ` · as of ${formatDate(scoring.as_of)}` : ''}. Not a health-risk, safety, compliance or purchase-probability score.</p>
    {scoring.context_note && <details className="score-model-notes"><summary>Model rules, exclusions and evidence limits</summary>
      {scoring.notes?.map(note => <p key={note}>{note}</p>)}<p>{scoring.context_note}</p>
      <p>The strongest recent official building follow-up or inspection finding is used, not both. PHH is recognized as public-health-hazard severity. Exact-ticket dismissed citations are excluded. Older findings decay after 90 and 180 days. Sampling points allow the five-day publication window; explicit cooling-tower projects without a published sign-off are bounded to 90 days.</p>
      <p>Point weights are transparent research-priority rules, not statistically calibrated predictions. The model has correctness and scenario tests, not demonstrated predictive accuracy.</p>
      {(scoring.uncapped_score ?? 0) > 100 && <p>The uncapped total is {scoring.uncapped_score}; displayed component points are limited to the overall 100-point maximum.</p>}
      <a href="data/priority-model-review.json" target="_blank" rel="noreferrer">Before / after model review ↗</a>
    </details>}
  </section>
}
