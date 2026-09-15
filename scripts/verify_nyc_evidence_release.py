"""Seal the exact tested NYC runtime and verify only that runtime during promotion."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.request import urlopen

BASE = 'https://jeremyhennessy.github.io/TowerSignal/'
MARKER = 'nyc-evidence-release.json'

def read(p): return json.loads(p.read_text())
def digest(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def tree(): return subprocess.check_output(['git','rev-parse','HEAD^{tree}'], text=True).strip()
def inventory(root): return {str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
def save(p, data): p.write_text(json.dumps(data, indent=2)+'\n')

def check_hosted(root, full):
    names = ['index.html','data/systems.json','data/metadata.json','data/legionella-alerts.json','data/legionella-property-matches.json','data/coverage-audit.json']
    names += [u.lstrip('/').removeprefix('TowerSignal/') for u in re.findall(r'(?:src|href)="([^\"]+\.(?:js|css))"', (root/'index.html').read_text())]
    if full:
        names += [MARKER,'data/priority-model-review.json','data/changes.json']
        matches = read(root/'data/legionella-property-matches.json')
        names += [f'data/details/{sid[:2]}/{sid}.json' for sid, value in sorted(matches['by_system'].items()) if value['building_observations']]
    for name in names:
        expected = digest(root/name)
        for attempt in range(6):
            try:
                with urlopen(BASE+name+'?nyc-release='+str(time.time_ns()), timeout=90) as response:
                    actual = hashlib.sha256(response.read()).hexdigest()
                if expected != actual: raise RuntimeError('Hosted identity mismatch: '+name)
                break
            except Exception:
                if attempt == 5: raise
                time.sleep(5)
        print('Hosted SHA-256 verified', name, expected, flush=True)

def seal(root, proof):
    proof.mkdir(parents=True,exist_ok=True)
    metadata=read(root/'data/metadata.json')
    value={'candidate_sha':os.environ['GITHUB_SHA'],'candidate_tree':tree(),'candidate_run_id':int(os.environ['GITHUB_RUN_ID']),
           'source_runtime_run_id':35020424389,'source_runtime_sha':'4a1499fab419e0b9f2b3607410d54adcb523ca57',
           'reconciled_main_sha':'2b19b35871af5f4c0141fd1f2f8e1649d48676fc','source_generated_at':metadata['generated_at'],
           'priority_model_version':metadata['priority_model_version'],'scope':'NYC GitHub Pages only',
           'matching':read(root/'data/legionella-property-matches.json')['summary']}
    save(root/MARKER,value)
    save(proof/'integrity.json',{'release':value,'files':inventory(root)})

def integrity(root,proof):
    expected=read(proof/'integrity.json')
    assert expected['release']['candidate_tree']==tree(),'Checked out tree differs from tested candidate'
    assert expected['files']==inventory(root),'Candidate bytes changed after acceptance'
    print('Every sealed candidate file and exact Git tree verified',len(expected['files']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['baseline','seal','integrity','hosted']);p.add_argument('--site',type=Path,required=True);p.add_argument('--proof',type=Path,default=Path('proof'))
    a=p.parse_args()
    if a.mode=='seal': seal(a.site,a.proof)
    elif a.mode=='integrity': integrity(a.site,a.proof)
    else: check_hosted(a.site,a.mode=='hosted')
