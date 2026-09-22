"""Validate actual browser-produced PDF bytes, not just a visible export button."""
from pathlib import Path
import json
import fitz

paths = list(Path('test-results').rglob('approved-account-report-*.pdf'))
assert paths, 'No actual Account PDF was generated'
results = []
for path in paths:
    doc = fitz.open(path)
    assert len(doc) == 4, (path, len(doc))
    texts = [page.get_text() for page in doc]
    assert all(abs(page.rect.width - 612) < 1 and abs(page.rect.height - 792) < 1 for page in doc), 'Not Letter'
    assert 'What the records actually say' in texts[1]
    assert 'Three simple next steps' in texts[2]
    assert 'Every key fact has a source.' in texts[3]
    assert len(doc[3].get_links()) >= 18, 'Source and account links missing'
    assert all('Inter' in font[3] for font in doc[0].get_fonts()), 'Report typeface substituted'
    for page in doc:
        for word in page.get_text('words'):
            assert word[0] >= 34 and word[2] <= 578 and word[1] >= 25 and word[3] <= 780, (path, page.number, word)
    if '2000000407' in path.name:
        assert '805 Columbus Avenue' in texts[0]
        assert '$2,000' in texts[0]
        assert '0881344164' in texts[1]
        assert texts[1].count('Excluded from the findings score') == 2
        assert 'Columbus Square 805 LLC' in texts[2]
    if '2000014227' in path.name:
        assert 'No public Legionella sample date is shown' in texts[0]
        assert '805 Columbus' not in ''.join(texts)
    results.append({'path': str(path), 'pages': len(doc), 'size': [612, 792], 'source_page_links': len(doc[3].get_links()), 'selectable_text': True})
Path('test-results/account-pdf-preflight.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
