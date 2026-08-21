# TowerSignal

TowerSignal is a specialized commercial-intelligence product for cooling-tower service providers. It converts authoritative NYC public registration, reported Legionella sampling, and NYC Health inspection records into transparent, source-backed commercial research signals.

## Demo

Deployment target: `https://jeremyhennessy.github.io/TowerSignal/`

**Current status:** Build 001 deployment is configured but this URL is not described here as live until the hosted application has been deployed and verified in a browser.

## Current scope

Build 001 covers New York City cooling towers only. It does not provide owner compliance management, outreach automation, contact enrichment, subscriptions, predictive risk, or national coverage.

## Data sources

- NYC Cooling Tower Registrations — `y4fw-iqfr`
- NYC Cooling Tower System Inspection Results — `f9wb-g8mb`

The Pages workflow retrieves both official NYC Open Data sources at deployment time. Raw full-source files are not committed. The pipeline records source row counts, retrieval timestamps, source update timestamps, deduplicates the registration inventory by `system_id`, groups multi-row inspection violations into inspection objects, validates broad anomaly gates, and generates optimized static JSON.

## Signal semantics

- **Confirmed violation** — an official NYC Health inspection record contains a violation within the configured recent period. Evidence confidence: `CONFIRMED`.
- **Potential sampling gap** — the latest publicly reported Legionella sample date is more than 31 calendar days old. The 31-day requirement applies while a system is operating; TowerSignal does not have enough public information to prove continuous operating status. This is a verification signal, not a noncompliance determination. Evidence confidence: `VERIFY`.
- **No public sample date** — the current public registration record contains no usable reported sample date. Verify operating and sampling status independently. Evidence confidence: `VERIFY`.
- **Priority score** — deterministic 0–100 commercial research-priority score. It is not a health-risk score, regulatory-risk score, safety rating, or probability of noncompliance. Every assigned point is shown in the detail view. Current model: `1.0`.
- **Evidence confidence** — separate from priority score so commercially interesting records do not imply stronger evidence than the public record supports.

## Regulatory caveat

NYC Health rules effective May 8, 2026 require Legionella culture sampling at least monthly, with no more than 31 days between samples, during cooling-tower system operation. Qualified-person compliance inspections are required at least every 90 days. TowerSignal does **not** treat the BWSO government inspection dataset as the owner's required 90-day qualified-person inspection history. Rules and authoritative source metadata are versioned in `config/rules/nyc.json`.

TowerSignal provides commercial intelligence derived from public records. Signals are not legal advice, health advice, or definitive determinations of regulatory compliance. Public records may be incomplete or delayed. Verify current operating, testing, maintenance and compliance status before relying on a signal or contacting a property.

## Architecture

```text
NYC Open Data
    ↓
Python 3.12 retrieval / validation / normalization
    ↓
Deterministic signal + priority model
    ↓
Static summary JSON + per-system detail JSON
    ↓
React + TypeScript + Vite
    ↓
GitHub Pages (/TowerSignal/)
```

The frontend loads an optimized system summary file and fetches a per-system detail file only when the user opens a record. This avoids shipping the full raw inspection dataset to every browser.

## Local development

Fixture-based development does not require the NYC API:

```bash
python -m unittest discover -s tests/python -p 'test_*.py' -v
npm install
npm run dev
```

To build a current live-source dataset locally (network access required):

```bash
python scripts/build_data.py --output public/data
python scripts/verify_live_data.py --sample-size 5
npm run build
```

## Testing

```bash
npm run lint
npm run typecheck
npm test
python -m unittest discover -s tests/python -p 'test_*.py' -v
npm run build
```

The Pages workflow also runs an independent five-system source comparison and Playwright browser verification against the deployed GitHub Pages URL in desktop Chromium and iPhone-sized contexts.

## Deployment

`.github/workflows/pages.yml` runs on pushes to `main`, manual dispatch, and a daily schedule. A failed authoritative-source retrieval, incomplete pagination, schema anomaly, data-quality gate, test, build, deployment, or hosted browser verification causes the workflow to fail rather than intentionally publish an empty substitute dataset. GitHub Pages retains the previous successful deployment when a new deployment never reaches the deploy step.

## Current status

Build 001 source implementation is under development on an isolated feature branch. This section will be updated only after CI, Pages deployment, hosted browser verification, and source comparisons are confirmed.
