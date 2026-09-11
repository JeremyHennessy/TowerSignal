from pathlib import Path

path = Path('tests/frontend/App.test.tsx')
text = path.read_text(encoding='utf-8')
old = '''  await user.click(screen.getByText('10 ALPHA ST'))
  await waitFor(() => expect(screen.getByRole('heading', { name:'Identity' })).toBeInTheDocument())
  expect(window.location.hash).toBe('#/account/SYS-1')
  expect(screen.getByRole('button', { name:'Copy account link' })).toBeInTheDocument()
  const detailPanel = screen.getByRole('complementary', { name: 'Selected cooling tower detail' })
  expect(within(detailPanel).getByRole('heading', { name:'Pre-visit field pack' })).toBeInTheDocument()
  expect(within(detailPanel).getByText('Schematics / mechanical drawings')).toBeInTheDocument()
  expect(within(detailPanel).getByText('Potential sampling gap')).toBeInTheDocument()
  expect(within(detailPanel).getByRole('heading', { name:'DOB NOW project activity' })).toBeInTheDocument()
  expect(within(detailPanel).getByText('Cooling tower mention')).toBeInTheDocument()
  expect(within(detailPanel).getByText('Replace existing cooling tower and associated piping.')).toBeInTheDocument()'''
new = '''  await user.click(screen.getByText('10 ALPHA ST'))
  await waitFor(() => expect(screen.getByRole('heading', { name:'What matters before the next action' })).toBeInTheDocument())
  expect(window.location.hash).toBe('#/account/SYS-1')
  expect(screen.getByRole('button', { name:'Copy account link' })).toBeInTheDocument()
  const detailPanel = screen.getByRole('complementary', { name: 'Selected cooling tower detail' })
  expect(within(detailPanel).getByText('Potential sampling gap')).toBeInTheDocument()

  await user.click(within(detailPanel).getByRole('button', { name: /^Evidence/ }))
  await waitFor(() => expect(within(detailPanel).getByRole('heading', { name:'Identity' })).toBeInTheDocument())
  expect(within(detailPanel).getByRole('heading', { name:'DOB NOW project activity' })).toBeInTheDocument()
  expect(within(detailPanel).getByText('Cooling tower mention')).toBeInTheDocument()
  expect(within(detailPanel).getByText('Replace existing cooling tower and associated piping.')).toBeInTheDocument()

  await user.click(within(detailPanel).getByRole('button', { name: /^Field/ }))
  await waitFor(() => expect(within(detailPanel).getByRole('heading', { name:'Pre-visit field pack' })).toBeInTheDocument())
  expect(within(detailPanel).getByText('Schematics / mechanical drawings')).toBeInTheDocument()'''
if text.count(old) != 1:
    raise SystemExit(f'Expected one legacy account assertion block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
