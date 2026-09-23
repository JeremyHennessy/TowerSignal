from __future__ import annotations
import csv,hashlib,json,os,tempfile,time
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage34');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
HOST='https://health.data.ny.gov';ID='j63k-4n92'
FIELDS=(
"locality","street_address","zip_code","state","lead_gooseneck_pigtail_or","current_public_side_sl",
"was_public_sl_material_ever","public_sl_material","public_sl_installation_or","public_sl_size",
"customer_sl_material","customer_sl_material_1","lead_solder_present","building_type",
"pou_or_poe_treatment_present","customer_sl_installation","customer_sl_size","sl_category","note","location")
UA={'User-Agent':'TowerSignal-independent-lsli-source-proof/20260923'}
REQ=[]

def get_json(url,timeout=120):
    last=None
    for i in range(4):
        try:
            req=ur.Request(url,headers=UA)
            with ur.urlopen(req,timeout=timeout) as r:
                b=r.read();REQ.append({'url':url,'status':r.status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()});return json.loads(b)
        except Exception as ex:
            REQ.append({'url':url,'error':type(ex).__name__});last=ex;time.sleep(min(2**i,8))
    raise RuntimeError(f'{url}: {last}')
served=get_json(LIVE+'data/nys-service-line-inventory-summary.json')
source=served.get('source') or {}
meta_url=f'{HOST}/api/views/{ID}'
m0=get_json(meta_url)
count0=int(get_json(f'{HOST}/resource/{ID}.json?'+up.urlencode({'$select':'count(*) as count'}))[0]['count'])
published=tuple(str(c.get('fieldName')) for c in m0.get('columns',[]) if c.get('fieldName') and not str(c.get('fieldName')).startswith(':@computed_region_'))
if published!=FIELDS:raise RuntimeError(f'Schema differs: {published}')
select=','.join(f'{f} AS {f}' for f in FIELDS)
url=f'{HOST}/resource/{ID}.csv?'+up.urlencode({'$select':select,'$limit':5000000})
fd,path=tempfile.mkstemp(prefix='lsli-audit-',suffix='.csv');os.close(fd);p=Path(path)
sha=hashlib.sha256();bytes_=0
try:
    req=ur.Request(url,headers={**UA,'Accept':'text/csv'})
    with ur.urlopen(req,timeout=900) as r,p.open('wb') as out:
        while True:
            b=r.read(1024*1024)
            if not b:break
            out.write(b);sha.update(b);bytes_+=len(b)
    rows=0
    with p.open('r',encoding='utf-8-sig',errors='replace',newline='') as h:
        reader=csv.reader(h)
        header=tuple(next(reader))
        if header!=FIELDS:raise RuntimeError(f'Header differs: {header}')
        for _ in reader:rows+=1
finally:
    p.unlink(missing_ok=True)
m1=get_json(meta_url)
count1=int(get_json(f'{HOST}/resource/{ID}.json?'+up.urlencode({'$select':'count(*) as count'}))[0]['count'])
digest=sha.hexdigest()
summary={
 'dataset_id':ID,
 'served_generated_at':served.get('generated_at'),
 'served_source_record_count':source.get('source_record_count'),
 'served_bulk_export_sha256':source.get('bulk_export_sha256'),
 'served_bulk_export_byte_count':source.get('bulk_export_byte_count'),
 'current_count_before':count0,'current_count_after':count1,'downloaded_rows':rows,'downloaded_bytes':bytes_,'downloaded_sha256':digest,
 'rows_updated_before':m0.get('rowsUpdatedAt'),'rows_updated_after':m1.get('rowsUpdatedAt'),
 'data_updated_before':m0.get('dataUpdatedAt'),'data_updated_after':m1.get('dataUpdatedAt'),
 'snapshot_stable':count0==count1==rows and m0.get('rowsUpdatedAt')==m1.get('rowsUpdatedAt') and m0.get('dataUpdatedAt')==m1.get('dataUpdatedAt'),
 'record_count_equal_served':rows==source.get('source_record_count'),
 'bulk_sha256_equal_served':digest==source.get('bulk_export_sha256'),
 'bulk_byte_count_equal_served':bytes_==source.get('bulk_export_byte_count'),
 'exact_current_bulk_snapshot_equal_served':rows==source.get('source_record_count') and digest==source.get('bulk_export_sha256') and bytes_==source.get('bulk_export_byte_count'),
 'source_fields_equal':list(FIELDS)==source.get('source_fields'),
 'boundary':'Independent complete current bulk export using the same authoritative 20-field schema. Exact SHA/byte equality proves the served source snapshot bytes when equal; it does not by itself re-prove every normalized row field.'
}
(OUT/'nys-lsli-bulk-source-proof.json').write_text(json.dumps(summary,indent=2))
(OUT/'requests.json').write_text(json.dumps(REQ,indent=2))
print(json.dumps(summary,indent=2))
