"""Checksum-pinned NYC-only candidate assembly and exact-byte hosted acceptance."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

BASE='https://jeremyhennessy.github.io/TowerSignal/'
SOURCE_RUN=34997430388
SOURCE_SHA='7eeb4a47e4be92ee8d9e16640705c97e8b93496b'
MARKER='nyc-evidence-release.json'

def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def load(path): return json.loads(path.read_text())
def save(path,value): path.write_text(json.dumps(value,indent=2)+'\n')
def code_tree(): return subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()
def files(root): return {str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
def hosted_matches(root, names):
    for name in names:
        last=None
        for attempt in range(8):
            try:
                with urlopen(BASE+name+'?verification='+str(time.time_ns()),timeout=90) as r:
                    actual=hashlib.sha256(r.read()).hexdigest()
                if actual != digest(root/name): raise RuntimeError('Hosted bytes differ: '+name)
                print('Hosted SHA-256 verified:',name,actual,flush=True)
                last=None
                break
            except Exception as exc:
                last=exc
                if attempt<7: time.sleep(5)
        if last: raise last

def baseline_identity(root):
    names=['index.html','data/metadata.json','data/systems.json','data/changes.json','data/legionella-alerts.json']
    names += [u.removeprefix('/TowerSignal/') for u in re.findall(r'(?:src|href)="([^\"]+\.(?:js|css))"',(root/'index.html').read_text())]
    hosted_matches(root,names)

def seal(root,proof):
    proof.mkdir(parents=True,exist_ok=True)
    marker={'candidate_sha':os.environ['GITHUB_SHA'],'candidate_tree':code_tree(),
            'candidate_run_id':int(os.environ['GITHUB_RUN_ID']),'source_pages_run':SOURCE_RUN,'source_pages_sha':SOURCE_SHA,
            'source_generated_at':load(root/'data/metadata.json')['generated_at'],
            'scope':'NYC GitHub Pages only','model_version':'1.1',
            'building_matching':load(root/'data/legionella-tower-links.json')['summary']}
    save(root/MARKER,marker)
    save(proof/'candidate-integrity.json',{'release':marker,'sha256':files(root)})

def integrity(root,proof):
    manifest=load(proof/'candidate-integrity.json')
    assert code_tree()==manifest['release']['candidate_tree'],'Current main tree differs from the exact tested candidate'
    assert files(root)==manifest['sha256'],'Candidate artifact bytes do not match sealed inventory'
    print('Exact tested tree and every candidate file verified',len(manifest['sha256']),flush=True)

def hosted(root):
    names=[MARKER,'index.html','data/metadata.json','data/systems.json','data/changes.json','data/legionella-alerts.json',
           'data/legionella-tower-links.json','data/priority-model-review.json','data/source-health.json']
    names += ['assets/'+p.name for p in (root/'assets').iterdir() if p.suffix in ('.js','.css')]
    links=load(root/'data/legionella-tower-links.json')
    # Every matched building account is checked, not just the headline table.
    names += ['data/details/'+sid[:2]+'/'+sid+'.json' for sid in sorted(links['by_system'])]
    hosted_matches(root,names)
    print('Hosted candidate and all matched-system details verified',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['baseline','seal','integrity','hosted']);p.add_argument('--site',type=Path,required=True);p.add_argument('--proof',type=Path,default=Path('proof'))
    a=p.parse_args()
    if a.mode=='baseline': baseline_identity(a.site)
    elif a.mode=='seal': seal(a.site,a.proof)
    elif a.mode=='integrity': integrity(a.site,a.proof)
    else: hosted(a.site)
