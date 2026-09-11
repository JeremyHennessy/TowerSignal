"""Recover one checksum-pinned Pages artifact; no build, collection or data writes."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import zipfile
from migrate_data_to_blob import GitHubReader, safe_path

SOURCE_RUN = 34544249376
SOURCE_SHA = '53f7016404774821051e5ebd02eeb5382dded55f'
ARTIFACT = 10181150350
ZIP_SHA256 = 'e1672458b40c4b77d92b0f47b7fe84a32ef54920a7fa4af1cb70e4c1bb8f975c'
BASE = 'https://jeremyhennessy.github.io/TowerSignal/'
ROOT = Path('.site-recovery')


def save(name, value):
    (ROOT/'proof').mkdir(parents=True, exist_ok=True)
    (ROOT/'proof'/name).write_text(json.dumps(value, indent=2)+'\n')


def prepare():
    reader=GitHubReader()
    run=reader.get(f'/actions/runs/{SOURCE_RUN}')
    assert run['head_sha']==SOURCE_SHA and run['conclusion']=='success' and run['status']=='completed'
    assert run['workflow_id']==339705737 and run['head_branch']=='main'
    result=reader.get(f'/actions/runs/{SOURCE_RUN}/jobs?filter=latest&per_page=100')
    assert result['total_count']==len(result['jobs'])
    jobs={j['name']:j for j in result['jobs']}
    assert all(jobs[n]['conclusion']=='success' for n in ['build','deploy','verify','persist-history'])
    meta=reader.get(f'/actions/artifacts/{ARTIFACT}')
    assert not meta['expired'] and meta['name']=='github-pages'
    assert meta['workflow_run']['id']==SOURCE_RUN and meta['workflow_run']['head_sha']==SOURCE_SHA
    assert meta['digest']=='sha256:'+ZIP_SHA256
    archive=ROOT/'source.zip'; reader.download(f'/actions/artifacts/{ARTIFACT}/zip',archive)
    assert archive.stat().st_size==meta['size_in_bytes']
    with archive.open('rb') as stream: assert hashlib.file_digest(stream,'sha256').hexdigest()==ZIP_SHA256
    directory=ROOT/'archive';directory.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        assert z.namelist()==['artifact.tar']
        with z.open('artifact.tar') as src,(directory/'artifact.tar').open('xb') as dst:
            shutil.copyfileobj(src,dst,4*1024**2)
    records={};runtime=0;html=None;total=0
    with tarfile.open(directory/'artifact.tar','r:') as tar:
        for item in tar:
            if item.isdir():continue
            assert item.isfile(), 'Non-regular member in verified site'
            name=safe_path(item.name.removeprefix('./'))
            assert name not in records
            total+=item.size;assert total<8*1024**3
            stream=tar.extractfile(item);sha=hashlib.sha256()
            if name=='index.html':
                data=stream.read();html=data.decode();sha.update(data)
            else:
                while block:=stream.read(4*1024**2):sha.update(block)
            records[name]={'bytes':item.size,'sha256':sha.hexdigest()}
            runtime+=name.startswith('data/')
    assert html and runtime==21990 and len(records)<100000
    assert 'id="root"' in html
    required=['index.html','data/systems.json','data/nys-systems.json','data/changes.json','data/companies.json','data/known-firms.json','data/source-health.json']
    required += [p for p in records if p.startswith('assets/') and p.endswith(('.js','.css'))]
    for prefix in ['data/details/','data/firm-details/']:
        required += sorted(n for n in records if n.startswith(prefix) and n.endswith('.json'))[:3]
    for link in re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"',html):
        path=link.lstrip('/').removeprefix('TowerSignal/')
        assert path in records
    assert all(n in records for n in required)
    history=reader.get('/git/ref/heads/data/towersignal-history')['object']['sha']
    save('source.json',{'source_run':SOURCE_RUN,'source_sha':SOURCE_SHA,'artifact':ARTIFACT,'zip_sha256':ZIP_SHA256,'runtime_files':runtime,'total_files':len(records),'bytes':total,'history_sha_before':history,'recovery_commit':os.environ['GITHUB_SHA']})
    save('hosted-manifest.json',{n:records[n] for n in sorted(set(required))})
    save('full-manifest.json',records)
    print(json.dumps({'verified_original_artifact':ARTIFACT,'runtime_files':runtime,'total_files':len(records),'hosted_checks':len(set(required))}))


def verify():
    manifest=json.loads((ROOT/'proof/hosted-manifest.json').read_text())
    results=[]
    for name,record in manifest.items():
        for attempt in range(8):
            try:
                request=Request(urljoin(BASE,name)+'?recovery='+str(time.time_ns()),headers={'Cache-Control':'no-cache'})
                with urlopen(request,timeout=90) as r:
                    data=r.read(record['bytes']+1)
                    assert r.status==200 and len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
                results.append(name);break
            except (HTTPError,URLError,TimeoutError,AssertionError):
                if attempt==7:raise RuntimeError('Hosted bytes not restored: '+name) from None
                time.sleep(5)
    source=json.loads((ROOT/'proof/source.json').read_text())
    history=GitHubReader().get('/git/ref/heads/data/towersignal-history')['object']['sha']
    save('hosted-result.json',{'status':'PASS','base_url':BASE,'files_verified':len(results),'source':source,'verified_paths':results,'history_sha_after':history,'history_changed_since_prepare':history!=source['history_sha_before'],'collection_run':False,'blob_accessed':False})
    print('HOSTED_BYTES_VERIFIED='+str(len(results)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=['prepare','verify'])
    args=parser.parse_args(); ROOT.mkdir(exist_ok=True)
    prepare() if args.operation=='prepare' else verify()
