"""Require actual NYC hosted bytes to match a preserved baseline or tested candidate."""
from pathlib import Path
from urllib.request import urlopen
import argparse
import hashlib
import json
import re
import time


def verify(root: Path, candidate: bool) -> None:
    base = 'https://jeremyhennessy.github.io/TowerSignal/'
    names = ['index.html', 'data/metadata.json', 'data/systems.json', 'data/legionella-alerts.json']
    names += [x.lstrip('/').removeprefix('TowerSignal/') for x in re.findall(r'(?:src|href)="([^\"]+\.(?:js|css))"', (root/'index.html').read_text())]
    if candidate:
        names += ['data/legionella-property-matches.json', 'home-intelligence-release.json']
        matches = json.loads((root/'data/legionella-property-matches.json').read_text())
        expected_registry = hashlib.sha256((root/'data/systems.json').read_bytes()).hexdigest()
        if matches['registry_sha256'] != expected_registry:
            raise SystemExit('Match index belongs to a different registry')
    for name in names:
        expected = hashlib.sha256((root/name).read_bytes()).hexdigest()
        for attempt in range(8):
            try:
                with urlopen(base+name+'?identity='+str(time.time_ns()), timeout=90) as response:
                    actual = hashlib.sha256(response.read()).hexdigest()
                if actual != expected:
                    raise RuntimeError('Hosted bytes differ: '+name)
                break
            except Exception:
                if attempt == 7:
                    raise
                time.sleep(5)
        print(name, expected, flush=True)
    print('Actual NYC HTML, assets and evidence identity verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    verify(args.root, args.candidate)
