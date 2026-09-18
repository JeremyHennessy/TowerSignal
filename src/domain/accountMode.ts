export type AccountView = 'summary' | 'sales' | 'field' | 'evidence' | 'history'

const accountViews = new Set<AccountView>(['summary', 'sales', 'field', 'evidence', 'history'])

export function normalizeAccountView(value: unknown): AccountView {
  return typeof value === 'string' && accountViews.has(value as AccountView) ? value as AccountView : 'summary'
}

export function accountViewFromHash(hash: string): AccountView {
  const raw = hash.replace(/^#\/?/, '')
  const [, query = ''] = raw.split('?')
  return normalizeAccountView(new URLSearchParams(query).get('view'))
}

export function accountHashWithView(hash: string, view: AccountView): string {
  const raw = hash.replace(/^#\/?/, '')
  const [path, query = ''] = raw.split('?')
  const params = new URLSearchParams(query)
  if (view === 'summary') params.delete('view')
  else params.set('view', view)
  const nextQuery = params.toString()
  return `#/${path}${nextQuery ? `?${nextQuery}` : ''}`
}
