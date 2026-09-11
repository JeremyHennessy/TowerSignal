from pathlib import Path
p = Path('tests/frontend/App.test.tsx')
text = p.read_text(encoding='utf-8')
old = "  expect(within(detailPanel).getByText('Replace existing cooling tower and associated piping.')).toBeInTheDocument()"
new = "  expect(within(detailPanel).getAllByText('Replace existing cooling tower and associated piping.').length).toBeGreaterThan(0)"
if text.count(old) != 1:
    raise SystemExit(f'Expected one DOB description assertion, found {text.count(old)}')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
