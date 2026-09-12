from pathlib import Path
p = Path('tests/frontend/App.test.tsx')
text = p.read_text(encoding='utf-8')
old = """  expect(within(detailPanel).getByText('Schematics / mechanical drawings')).toBeInTheDocument()
  expect(within(detailPanel).getByRole('heading', { name:'OATH case lifecycle' })).toBeInTheDocument()
  expect(within(detailPanel).getByRole('heading', { name:'TowerSignal History' })).toBeInTheDocument()
  expect(within(detailPanel).getByText(/Ticket 0880900460/)).toBeInTheDocument()
  expect(within(detailPanel).getByText('IN VIOLATION')).toBeInTheDocument()"""
new = """  expect(within(detailPanel).getByText('Schematics / mechanical drawings')).toBeInTheDocument()

  await user.click(within(detailPanel).getByRole('button', { name: /^History/ }))
  await waitFor(() => expect(within(detailPanel).getByRole('heading', { name:'OATH case lifecycle' })).toBeInTheDocument())
  expect(within(detailPanel).getByRole('heading', { name:'TowerSignal History' })).toBeInTheDocument()
  expect(within(detailPanel).getByText(/Ticket 0880900460/)).toBeInTheDocument()
  expect(within(detailPanel).getByText('IN VIOLATION')).toBeInTheDocument()"""
if text.count(old) != 1:
    raise SystemExit(f'Expected one field-to-history assertion block, found {text.count(old)}')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
