import { describe, expect, it } from 'vitest'
import { formatDate, formatTimestamp } from '../../src/domain/labels'

describe('date labels', () => {
  it('formats date-only source values', () => {
    expect(formatDate('2026-09-04')).toContain('2026')
    expect(formatDate('2026-09-04')).not.toContain('Invalid')
  })

  it('formats ISO timestamps when a date label is needed', () => {
    expect(formatDate('2026-08-22T13:45:00Z')).toContain('2026')
    expect(formatDate('2026-08-22T13:45:00Z')).not.toContain('Invalid')
  })

  it('returns a safe fallback for invalid or missing values', () => {
    expect(formatDate('not-a-date')).toBe('Not available')
    expect(formatTimestamp('not-a-date')).toBe('Not available')
    expect(formatDate(null)).toBe('Not available')
  })
})
