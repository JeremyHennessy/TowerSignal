"""Fail closed if any published demo image differs from the supplied deck extraction."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path('public'))
args = parser.parse_args()
manifest = json.loads(Path('docs/marketing/demo-deck-20260922.json').read_text())
assert manifest['source_sha256'] == 'c823956148d7706a302428960badfaa7cb6d03431ee719d37065f8c98cdcb571'
assert sorted(asset['pdf_page'] for asset in manifest['assets']) == list(range(1, 9))
size = 0
for asset in manifest['assets']:
    relative = Path(asset['path']).relative_to('public')
    assert relative.parts[:2] == ('marketing', 'demo-deck-20260922')
    payload = (args.root / relative).read_bytes()
    assert len(payload) == asset['size_bytes'], (relative, 'size changed')
    assert hashlib.sha256(payload).hexdigest() == asset['sha256'], (relative, 'checksum changed')
    assert payload[:4] == b'RIFF' and payload[8:12] == b'WEBP', (relative, 'not WebP')
    size += len(payload)
assert size < 2_000_000, 'Demo image payload exceeded the reviewed size budget'
print(f'All 8 original demo visuals verified: {size:,} bytes; no image substitution.')
