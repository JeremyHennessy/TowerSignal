from __future__ import annotations
import hashlib,json,os,re
from pathlib import Path

OUT=Path('.audit-stage28');OUT.mkdir(exist_ok=True)
ROOT='towersignal-data'
POINTER=ROOT+'/pointers/production-current.json'
PAGES_WORKFLOW=339705737
DATA_WORKFLOW='.github/workflows/azure-data-refresh.yml'

def safe_source(src):
    if not isinstance(src,dict):return None
    allowed=('kind','workflow_path','workflow_id','run_id','run_number','run_attempt','source_sha','created_at','history_sha')
    return {k:src.get(k) for k in allowed if k in src}

from azure.storage.blob import BlobServiceClient
account=os.environ['AZURE_STORAGE_ACCOUNT']
container=os.environ['AZURE_STORAGE_CONTAINER']
assert account=='pharm3r' and container=='data'
with BlobServiceClient(f'https://{account}.blob.core.windows.net',credential=os.environ['AZURE_STORAGE_KEY'],
                       retry_total=3,connection_timeout=15,read_timeout=60) as client:
    blob=client.get_blob_client(container=container,blob=POINTER)
    props=blob.get_blob_properties()
    raw=blob.download_blob(max_concurrency=1).readall()

value=json.loads(raw)
src=value.get('source') or {}
pages=src.get('workflow_id')==PAGES_WORKFLOW and not src.get('kind')
data_only=src.get('kind')=='data-only' and src.get('workflow_path')==DATA_WORKFLOW
report={
 'pointer':POINTER,
 'bytes':len(raw),
 'sha256':hashlib.sha256(raw).hexdigest(),
 'etag':str(props.etag),
 'schema_version':value.get('schema_version'),
 'domain':value.get('domain'),
 'source':safe_source(src),
 'runtime_descriptor_present':isinstance(value.get('runtime'),dict),
 'history_descriptor_present':isinstance(value.get('history'),dict),
 'pages_publisher_current_pointer_accepts':bool(value.get('schema_version')==1 and value.get('domain')=='TOWERSIGNAL_BLOB_RELEASE' and isinstance(src.get('run_number'),int) and src.get('workflow_id')==PAGES_WORKFLOW),
 'data_refresh_read_current_accepts':bool(value.get('schema_version')==1 and value.get('domain')=='TOWERSIGNAL_BLOB_RELEASE' and (pages or data_only) and re.fullmatch('[0-9a-f]{40}',str(src.get('source_sha') or '')) and isinstance(src.get('run_id'),int)),
 'source_kind_classification':'PAGES' if pages else ('DATA_ONLY' if data_only else 'OTHER'),
 'diagnosis':'POINTER_CONTRACT_INCOMPATIBILITY' if data_only else ('PAGES_POINTER' if pages else 'UNRECOGNIZED_POINTER'),
 'write_performed':False,
}
(OUT/'blob-current-pointer-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
