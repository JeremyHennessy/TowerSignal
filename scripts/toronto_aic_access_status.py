from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toronto_market_common import read_json, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / 'data' / 'toronto' / 'market' / 'current'


def main() -> None:
    applications = read_json(MARKET / 'open_licensed/toronto_aic_applications.json') or {}
    rows = applications.get('applications') or []
    catalogue_count = len(rows)
    if catalogue_count <= 0:
        raise RuntimeError('AIC application catalogue is missing; cannot record document-access status')

    report: dict[str, Any] = {
        'schema_version': 'toronto-aic-access-1.0',
        'generated_at': utc_now(),
        'status': 'BLOCKED_EXTERNAL_ACCESS_CONTROL',
        'application_catalogue_records': catalogue_count,
        'catalogue_source': 'City of Toronto AIC FeatureServer layer 60',
        'current_public_page': 'https://www.toronto.ca/city-government/planning-development/application-details/',
        'current_read_apis': [
            'https://api.toronto.ca/aic/getapplicationdetails',
            'https://api.toronto.ca/aic/getapplicationattachments',
        ],
        'current_transport_contract': {
            'browser_javascript_observation': 'Current Toronto AIC JavaScript POSTs numeric folderRsn to the two api.toronto.ca/aic read endpoints and sends a browser-generated g-recaptcha-response header.',
            'server_probe_result': 'No-token, blank-token and fake-token probes returned HTTP 400 for both read endpoints.',
            'legacy_transport_result': 'The stored legacy secure.toronto.ca/AIC encrypted URLs returned HTTP 403 for almost all current applications in the attempted corpus partitions.',
            'representative_invalid_partition': {
                'workflow_run_id': 33217943951,
                'partition': 0,
                'applications': 495,
                'application_pages_fetched': 3,
                'application_page_fetch_errors': 492,
                'interpretation': 'This partition is retained only as transport diagnostics and is not counted as document-corpus coverage.'
            },
            'current_api_probe_run_id': 33220422803,
            'backend_trace_run_id': 33220200456,
        },
        'decision': {
            'automated_document_ingestion': 'BLOCKED',
            'reason': 'The current public supporting-document API is guarded by reCAPTCHA. TowerSignal will not defeat or bypass that anti-bot/access control for bulk extraction.',
            'metadata_ingestion': 'ALLOWED_AND_COMPLETED',
            'next_permitted_paths': [
                'City-provided documented bulk/API access that does not require bypassing reCAPTCHA',
                'written City permission or data feed',
                'manual review of specific applications for prospect/account verification',
                'other open-licensed City documents already exposed outside the reCAPTCHA-gated AIC attachment API',
            ],
        },
        'coverage_semantics': {
            'document_corpus_complete': False,
            'document_corpus_coverage_percent': None,
            'cooling_tower_candidates_from_aic_documents': None,
            'ocr_gap': None,
            'warning': 'Zero parsed AIC documents is not evidence that applications have no supporting documents.'
        },
    }
    write_json(MARKET / 'aic_transport_report.json', report)

    summary = {
        'schema_version': 'toronto-aic-corpus-summary-1.0',
        'generated_at': utc_now(),
        'status': 'BLOCKED_EXTERNAL_ACCESS_CONTROL',
        'applications_total_source': catalogue_count,
        'unique_applications_scanned': 0,
        'applications_in_shards': 0,
        'application_pages_fetched': 0,
        'application_page_fetch_errors': None,
        'documents_discovered': None,
        'documents_parsed': 0,
        'documents_fetch_errors': None,
        'target_document_count': None,
        'documents_with_mechanical_signals': None,
        'document_transport': report['current_transport_contract'],
        'coverage_caveat': report['coverage_semantics'],
    }
    write_json(MARKET / 'aic_corpus_summary.json', summary)
    write_json(MARKET / 'aic_document_index.json', {
        'schema_version': 'toronto-aic-document-index-1.0',
        'generated_at': utc_now(),
        'status': 'BLOCKED_EXTERNAL_ACCESS_CONTROL',
        'documents': [],
        'warning': report['coverage_semantics']['warning'],
    })
    write_json(MARKET / 'aic_application_scan_status.json', {
        'schema_version': 'toronto-aic-application-scan-status-1.0',
        'generated_at': utc_now(),
        'status': 'APPLICATION_CATALOGUE_COMPLETE_DOCUMENT_TRANSPORT_BLOCKED',
        'application_catalogue_records': catalogue_count,
        'document_scan_records': 0,
        'transport_report': 'aic_transport_report.json',
    })
    write_json(MARKET / 'aic_explicit_tower_candidates.json', {
        'schema_version': 'toronto-aic-explicit-tower-candidates-1.0',
        'generated_at': utc_now(),
        'status': 'NOT_MEASURED_DOCUMENT_TRANSPORT_BLOCKED',
        'documents': [],
        'candidate_count': None,
        'warning': 'AIC document candidates are unknown because the supporting-document corpus could not be lawfully automated through the current reCAPTCHA-gated public transport.'
    })
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
