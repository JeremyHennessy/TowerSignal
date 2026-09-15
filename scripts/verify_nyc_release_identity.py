"""Verify actual hosted NYC bytes against the unmodified Pages 34997430388 artifact."""
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json
import re
import sys
import time

root = Path(sys.argv[1])
base = 'https://jeremyhennessy.github.io/TowerSignal/'
paths = ['index.html', 'data/metadata.json', 'data/systems.json', 'data/legionella-alerts.json', 'data/details/20/2000000660.json', 'data/source-health.json']
paths += [x.lstrip('/').removeprefix('TowerSignal/') for x in re.findall(r'(?:src|href)="([^\"]+\.(?:js|css))"', (root/'index.html').read_text())]
for name in paths:
    expected = hashlib.sha256((root/name).read_bytes()).hexdigest()
    with urlopen(base+name+'?acceptance='+str(time.time_ns()), timeout=90) as response:
        actual = hashlib.sha256(response.read()).hexdigest()
    if actual != expected:
        raise SystemExit('Hosted release moved or differs from source artifact: '+name)
    print(name, actual, flush=True)
metadata = json.loads((root/'data/metadata.json').read_text())
if not metadata.get('property_enforcement_cache_available'):
    raise SystemExit('Expected deployed enforcement data is missing')
print('Exact NYC hosted source identity verified; no data substituted or regenerated.')
