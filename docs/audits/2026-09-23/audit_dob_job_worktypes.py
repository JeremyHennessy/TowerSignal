from __future__ import annotations
import json, hashlib, urllib.request as ur
from collections import Counter,defaultdict
from pathlib import Path

URL='https://jeremyhennessy.github.io/TowerSignal/data/nyc-water-signals.json'
with ur.urlopen(ur.Request(URL,headers={'User-Agent':'TowerSignal-readonly-worktype-audit'}),timeout=120) as r:
    raw=r.read()
payload=json.loads(raw)
rows=payload.get('dob_water_job_filings') or []
patterns=Counter(); category_patterns=Counter(); generic=[]; inconsistent=[]
for row in rows:
    source=row.get('raw') if isinstance(row.get('raw'),dict) else {}
    flags=tuple(name for name,key in [
      ('PLUMBING','plumbing_work_type'),
      ('MECHANICAL','mechanical_systems_work_type_'),
      ('BOILER','boiler_equipment_work_type_')
    ] if str(source.get(key) or '').strip().upper()=='YES')
    label='+'.join(flags) or 'NO_EXPLICIT_FLAG'
    patterns[label]+=1
    category=str(row.get('category') or '')
    category_patterns[(category,label)]+=1
    if category=='OTHER_WATER_MECHANICAL':
        generic.append({
          'source_record_id':row.get('source_record_id'),'bbl':row.get('bbl'),'bin':row.get('bin'),
          'category':category,'explicit_work_types':flags,'job_description':row.get('job_description'),
          'plumbing_work_type':row.get('plumbing_work_type'),'mechanical_work_type':row.get('mechanical_work_type'),
          'boiler_work_type':row.get('boiler_work_type')
        })
    if not flags:
        inconsistent.append({'source_record_id':row.get('source_record_id'),'category':category,'raw':source})
summary={
 'url':URL,'cache_sha256':hashlib.sha256(raw).hexdigest(),'rows':len(rows),
 'explicit_work_type_patterns':dict(patterns),
 'generic_other_water_mechanical_rows':len(generic),
 'generic_pattern_counts':dict(Counter('+'.join(x['explicit_work_types']) or 'NO_EXPLICIT_FLAG' for x in generic)),
 'rows_missing_all_required_explicit_flags':len(inconsistent),
 'category_pattern_counts':{f'{k[0]}|{k[1]}':v for k,v in sorted(category_patterns.items())},
 'diagnosis':'The collector query requires PLUMBING/MECHANICAL/BOILER YES, but classify_dob_work uses job_description plus generic work_type; job filings do not select a generic work_type. Explicit source work-type distinctions are retained but do not influence category.',
 'boundary':'This quantifies lost classification context. It does not assert a single correct replacement category for multi-flag records without a reviewed precedence rule.'
}
out=Path('.audit-stage8');out.mkdir(exist_ok=True)
(out/'dob-job-worktype-summary.json').write_text(json.dumps(summary,indent=2))
(out/'dob-job-generic-worktype-cases.json').write_text(json.dumps(generic,indent=2))
print(json.dumps(summary,indent=2))
