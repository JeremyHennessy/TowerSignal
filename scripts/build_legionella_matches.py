"""Publish additive, source-scoped article/building links without rewriting accounts or scores."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from towersignal.legionella_matching import collect_documents, match_documents


def build(data: Path, evidence_dir: Path | None = None) -> dict:
    original = (data/'systems.json').read_bytes()
    registry = json.loads(original)
    systems = registry['systems']
    if not systems or len({r['system_id'] for r in systems}) != len(systems):
        raise ValueError('Expected a nonempty unique system registry')
    documents = collect_documents(evidence_dir)
    payload = match_documents(documents, systems)
    payload['generated_at'] = datetime.now(timezone.utc).isoformat()
    payload['registry_generated_at'] = registry['metadata']['generated_at']
    payload['registry_sha256'] = hashlib.sha256(original).hexdigest()
    payload['schema_version'] = '1.0'
    ids = {str(r['system_id']) for r in systems}
    assert all(set(record['system_ids']) <= ids for record in payload['matched_observations'])
    assert len(payload['matched_observations']) + len(payload['unresolved']) == len(documents['observations'])
    assert all(record['match_scope'] == 'NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM' for record in payload['matched_observations'])
    if evidence_dir:
        (evidence_dir/'extracted-documents.json').write_text(json.dumps(documents, indent=2))
    path = data/'legionella-property-matches.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temporary.replace(path)
    assert (data/'systems.json').read_bytes() == original, 'Registry/scoring mutation refused'
    print(json.dumps(payload['summary'], indent=2))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--source-evidence', type=Path, default=None)
    args = parser.parse_args()
    build(args.data, args.source_evidence)
