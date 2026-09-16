"""NYC Monitor-only release proof: preserve every data byte and promote a sealed UI."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.request import urlopen
from verify_nyc_evidence_release import BASE, check_hosted, inventory, read, save, tree

MARKER='monitor-format-release.json'
SOURCE_SHA='30422453fd832df2baec74ff5ab10f4ecd3bf959'
SOURCE_RUN=35034217352
SOURCE_FILES={
'src/components/ChangesView.tsx':'b3e517149b1588c16d401c8815e2ed56f3f9c37fd88e01bbeb6f89e4c87dbcc6',
'src/domain/changePresentation.ts':'849e7db11c537414f3e0021e6b219f55c46f4c13d04dab659e833c7e6d40cd7c',
'src/domain/monitorFields.ts':'15eba119ef8c3c81fd9166b73e0566f3417d21f4a1a00d9c7ce58ce5ee971f19',
'src/styles/monitor-event-table.css':'868087a4efa50ca8c290435df772ec41049032178ac75915f25a716965dacafe',
 'tests/frontend/monitorFormatting.test.tsx':'f94d10c13352efb3ddf9a4936b47d1c308dd84e3d98e3880afd844283f9a7259',
 'tests/e2e/monitor-format.spec.ts':'4c93be8be28bb1b82db544ea7d26bae95f93f98fab30d780406800959035a26e'}

def prepare(root,baseline,proof):
    for name,expected in SOURCE_FILES.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,'Transferred source differs from locally tested file: '+name
    expected=inventory(baseline/'data')
    assert expected==inventory(root/'data'),'Formatting changed source data, scores, links or history'
    prior=read(baseline/'nyc-evidence-release.json')
    assert prior['candidate_sha']=='62bf803ce92bd469757df63030bac66338572253'
    for marker in baseline.glob('*.json'):
        shutil.copy2(marker,root/marker.name)
    value={'candidate_sha':os.environ['GITHUB_SHA'],'candidate_tree':tree(),'candidate_run_id':int(os.environ['GITHUB_RUN_ID']),
      'source_sha':SOURCE_SHA,'source_release_run':SOURCE_RUN,'scope':'NYC Monitor presentation only',
      'source_generated_at':read(root/'data/metadata.json')['generated_at'],'unchanged_data_files':len(expected),
      'source_data_inventory_sha256':hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest()}
    proof.mkdir(parents=True,exist_ok=True)
    save(root/MARKER,value);save(proof/'integrity.json',{'release':value,'files':inventory(root)})
    save(proof/'unchanged-data.json',{'baseline_release':SOURCE_RUN,'data_files':len(expected),'changed_data_files':0,'source_sha256':expected})
    print(json.dumps(value,indent=2))

def integrity(root,proof):
    expected=read(proof/'integrity.json')
    assert expected['release']['candidate_tree']==tree(),'Merged source tree is not the tested candidate'
    assert expected['files']==inventory(root),'Sealed candidate bytes differ'
    assert read(proof/'unchanged-data.json')['source_sha256']==inventory(root/'data'),'Source data changed after candidate acceptance'
    print('Every candidate file and every unchanged source-data file verified',len(expected['files']))

def hosted(root):
    check_hosted(root,True)
    expected=hashlib.sha256((root/MARKER).read_bytes()).hexdigest()
    with urlopen(BASE+MARKER+'?verify='+str(time.time_ns()),timeout=90) as response:
        assert hashlib.sha256(response.read()).hexdigest()==expected,'Hosted Monitor release marker differs'
    print('Actual hosted Monitor identity verified',expected)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['baseline','prepare','integrity','hosted']);p.add_argument('--site',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--proof',type=Path,default=Path('proof'));a=p.parse_args()
    if a.mode=='prepare': prepare(a.site,a.baseline,a.proof)
    elif a.mode=='integrity': integrity(a.site,a.proof)
    elif a.mode=='baseline': check_hosted(a.site,True)
    else: hosted(a.site)
