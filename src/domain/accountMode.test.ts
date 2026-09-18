import { describe, expect, it } from 'vitest'
import { accountHashWithView, accountViewFromHash, normalizeAccountView } from './accountMode'

describe('account mode route state', () => {
  it('normalizes unknown values to Summary', () => {
    expect(normalizeAccountView('evidence')).toBe('evidence')
    expect(normalizeAccountView('other')).toBe('summary')
    expect(normalizeAccountView(null)).toBe('summary')
  })

  it('restores account modes from hash query state', () => {
    expect(accountViewFromHash('#/account/2000015564?view=history')).toBe('history')
    expect(accountViewFromHash('#/account/2000015564')).toBe('summary')
  })

  it('preserves unrelated query parameters and omits the default Summary view', () => {
    expect(accountHashWithView('#/account/2000015564?foo=bar', 'evidence')).toBe('#/account/2000015564?foo=bar&view=evidence')
    expect(accountHashWithView('#/account/2000015564?foo=bar&view=evidence', 'summary')).toBe('#/account/2000015564?foo=bar')
  })
})
