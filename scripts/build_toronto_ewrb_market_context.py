from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/toronto/warehouse/current/open_licensed/ontario_ewrb_large_buildings.json'
OUTPUT = ROOT / 'public/data/toronto-ewrb-market.json'


def clean_text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    return '' if text.casefold() in {'', 'nan', 'none', 'null', 'not available', 'n/a'} else text


def is_numeric(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def primary_type(row: dict[str, Any]) -> str:
    return clean_text(row.get('PrimPropTypCalc')) or clean_text(row.get('PrimPropTypSelf')) or 'Unknown / not published'


def certification_value(row: dict[str, Any]) -> str:
    return clean_text(row.get('Ener_Star_Certs')) or clean_text(row.get('Energy_Star_Certs'))


def build() -> dict[str, Any]:
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    metadata = source.get('metadata') or {}
    rows = [row for row in source.get('toronto_rows', []) if isinstance(row, dict)]

    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        year = row.get('_towersignal_source_year')
        if isinstance(year, int):
            by_year[year].append(row)

    annual = []
    for year in sorted(by_year):
        year_rows = by_year[year]
        ewrb_ids = {clean_text(row.get('EWRB_ID')) for row in year_rows if clean_text(row.get('EWRB_ID'))}
        quality_yes = sum(clean_text(row.get('Data_Qual_Check')).casefold() == 'yes' for row in year_rows)
        numeric_scores = sum(is_numeric(row.get('Ener_Star_Score')) for row in year_rows)
        certification_values = sum(bool(certification_value(row)) for row in year_rows)
        type_counts = Counter(primary_type(row) for row in year_rows)
        fsa_counts = Counter(clean_text(row.get('Postal_Code')).upper()[:3] for row in year_rows if clean_text(row.get('Postal_Code')).upper().startswith('M'))
        annual.append({
            'year': year,
            'reporting_rows': len(year_rows),
            'unique_ewrb_ids': len(ewrb_ids),
            'data_quality_check_yes_rows': quality_yes,
            'data_quality_check_yes_percent': round(quality_yes / len(year_rows) * 100, 1) if year_rows else None,
            'energy_star_numeric_score_rows': numeric_scores,
            'published_energy_star_certification_value_rows': certification_values,
            'top_property_types': [{'property_type': key, 'rows': count} for key, count in type_counts.most_common(10)],
            'top_postal_fsa': [{'fsa': key, 'rows': count} for key, count in fsa_counts.most_common(10)],
        })

    all_types = Counter(primary_type(row) for row in rows)
    all_fsas = Counter(clean_text(row.get('Postal_Code')).upper()[:3] for row in rows if clean_text(row.get('Postal_Code')).upper().startswith('M'))
    resource_years = sorted({item.get('year') for item in metadata.get('resources', []) if isinstance(item, dict) and isinstance(item.get('year'), int)})

    payload = {
        'schema_version': 'toronto-ewrb-market-1.0',
        'scope': 'TORONTO_AGGREGATE_ONLY',
        'source_key': metadata.get('key') or 'ontario_ewrb_large_buildings',
        'title': metadata.get('title') or 'Energy and water usage of large buildings in Ontario',
        'catalogue_url': metadata.get('catalogue_url'),
        'license': metadata.get('license'),
        'retrieved_at': metadata.get('retrieved_at'),
        'reporting_years': resource_years,
        'latest_reporting_year': max(resource_years) if resource_years else None,
        'toronto_reporting_rows': len(rows),
        'annual': annual,
        'overall_top_property_types': [{'property_type': key, 'rows': count} for key, count in all_types.most_common(15)],
        'overall_top_postal_fsa': [{'fsa': key, 'rows': count} for key, count in all_fsas.most_common(15)],
        'identity_contract': {
            'property_level_links': 0,
            'reason': 'The public Ontario EWRB disclosure does not include civic street address or assessment roll number. EWRB ID, city, and postal FSA are not sufficient to create a deterministic TowerSignal property identity.',
            'allowed_use': 'Aggregate Toronto market benchmarking only until an independent lawful address-bearing bridge is available.',
            'tower_evidence_effect': 'NONE',
            'relationship_effect': 'NONE',
        },
        'absence': metadata.get('absence') or 'No row is not evidence that a property has no relevant equipment, activity, or compliance history.',
    }
    return payload


def main() -> None:
    payload = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': 'PASSED',
        'output': str(OUTPUT.relative_to(ROOT)),
        'toronto_reporting_rows': payload['toronto_reporting_rows'],
        'reporting_years': payload['reporting_years'],
        'property_level_links': payload['identity_contract']['property_level_links'],
    }, indent=2))


if __name__ == '__main__':
    main()
