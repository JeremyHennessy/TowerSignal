"""Build a separately versioned outbreak-to-registry relationship cache."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from towersignal.legionella_tower_links import build_payload, collect_documents, fingerprint  # noqa: E402


def build(data: Path, previous: Path | None = None, source_dir: Path | None = None) -> dict:
    systems = json.loads((data / 'systems.json').read_text())
    alerts = json.loads((data / 'legionella-alerts.json').read_text())
    prior = json.loads(previous.read_text()) if previous and previous.exists() else None
    documents = collect_documents()
    collected_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    payload = build_payload(systems['systems'], documents, alerts, collected_at=collected_at, previous=prior)
    if source_dir:
        source_dir.mkdir(parents=True, exist_ok=True)
        for url, content in documents.items():
            (source_dir / (fingerprint(content) + ('.pdf' if url.endswith('.pdf') else '.html'))).write_bytes(content)
    for row in systems['systems']:
        links = payload['system_links'].get(row['system_id'], [])
        row['legionella_event_ids'] = [item['event_id'] for item in links]
        row['legionella_named_event_ids'] = [item['event_id'] for item in links if item['relationship'] == 'NAMED_BUILDING']
        row['legionella_area_only_event_ids'] = [item['event_id'] for item in links if item['relationship'] == 'AREA_CONTEXT']
    for name, value in [('legionella-tower-links.json', payload), ('systems.json', systems)]:
        target = data / name
        tmp = target.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
        tmp.replace(target)
    print(json.dumps({'generated_at': collected_at, 'events': [{key: e[key] for key in ('event_id','published_building_count','named_building_count','named_system_count','area_only_system_count','unresolved_building_count')} for e in payload['events']]}, indent=2))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT / 'public/data')
    parser.add_argument('--previous-cache', type=Path)
    parser.add_argument('--source-dir', type=Path)
    args = parser.parse_args()
    build(args.data, args.previous_cache, args.source_dir)
