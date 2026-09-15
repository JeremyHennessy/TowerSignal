import { describe, expect, it } from 'vitest'
import type { SystemsPayload } from '../../src/types/data'
import { enforcementCoverage, legionellaChannelRows, parseLegionellaHealth, requiredLegionellaChannels, safeSourceUrl } from '../../src/domain/sourceHealthExpansion'

function systems(): SystemsPayload {
  return {
    metadata: { sources: [{ dataset_id: 'wvxf-dwi5', name: 'HPD', retrieved_at: '2026-09-15T15:00:00Z', source_record_count: 9000, matched_record_count: 7, source_last_updated_at: null, url: 'https://data.cityofnewyork.us/d/wvxf-dwi5' }] },
    systems: [
      { system_id: 'one', bbl: '1000010001', bin: '1000001', hpd_violation_count: 7 },
      { system_id: 'two', bbl: '1000010001', bin: '1000001', hpd_violation_count: 7 },
      { system_id: 'three', bbl: '1000020001', bin: '1000002', hpd_violation_count: 0 },
    ],
  } as unknown as SystemsPayload
}

function alerts() {
  return {
    domain: 'LEGIONELLA_PUBLIC_HEALTH_ALERTS', generated_at: '2026-09-15T16:00:00Z',
    source_channels: requiredLegionellaChannels.map(([key]) => ({ channel_key: key, retrieved_at: '2026-09-15T14:00:00Z', content_sha256: 'a'.repeat(64), url: 'https://www.nyc.gov/' })),
    items: [{ item_id: 'old', retrieved_at: '2026-09-01T00:00:00Z' }], errors: [],
    summary: { source_channel_count: 12, discovered_relevant_item_count: 1, retrieval_error_count: 0 },
    history_merge: { retained_prior_item_count: 1, current_collection_item_count: 0, merged_item_count: 1 },
  }
}

describe('property enforcement source coverage', () => {
  it('separates citywide rows, retained records, property identities and represented systems', () => {
    const before = systems()
    const original = JSON.stringify(before)
    const row = enforcementCoverage(before)[0]
    expect(row.sourceRecords).toBe(9000)
    expect(row.records).toBe(7)
    expect(row.requested).toBe(2)
    expect(row.matched).toBe(1)
    expect(row.attached).toBe(2)
    expect(row.coverage).toBeCloseTo(66.6667, 3)
    expect(row.available).toBe(true)
    expect(JSON.stringify(before)).toBe(original)
  })
  it('does not invent zeros or healthy states for an absent source', () => {
    const row = enforcementCoverage(systems())[1]
    expect(row.available).toBe(false)
    expect(row.records).toBeNull()
    expect(row.attached).toBeNull()
    expect(row.matched).toBeNull()
    expect(row.coverage).toBeNull()
  })
  it('does not interpret missing attachment measurements as zero coverage', () => {
    const value = systems()
    value.systems.push({ system_id: 'missing', bbl: null, bin: null } as SystemsPayload['systems'][number])
    expect(enforcementCoverage(value)[0].attached).toBeNull()
    expect(enforcementCoverage(value)[0].available).toBe(false)
  })
  it('keeps observed zero distinct from missing data', () => {
    const value = systems()
    value.metadata.sources[0].matched_record_count = 0
    value.systems = [{ system_id: 'none', bbl: '1000010001', bin: '1000001', hpd_violation_count: 0 }] as unknown as SystemsPayload['systems']
    expect(enforcementCoverage(value)[0]).toMatchObject({ records: 0, attached: 0, matched: 0, coverage: 0, available: true })
  })
})

describe('Legionnaires source health', () => {
  it('reads the actual source_channels snapshot contract, not a nonexistent source_snapshots field', () => {
    const value = parseLegionellaHealth(alerts())
    const rows = legionellaChannelRows(value)
    expect(rows).toHaveLength(12)
    expect(rows.every(row => row.retrieved)).toBe(true)
    expect(rows[0].retrievedAt).toBe('2026-09-15T14:00:00Z')
    expect(value.items[0].retrieved_at).toBe('2026-09-01T00:00:00Z')
    expect(value.history_merge?.retained_prior_item_count).toBe(1)
  })
  it('keeps a missing required channel visible as unverified', () => {
    const value = alerts()
    value.source_channels.pop()
    value.summary.source_channel_count = 11
    const rows = legionellaChannelRows(parseLegionellaHealth(value))
    expect(rows).toHaveLength(12)
    expect(rows.filter(row => !row.retrieved)).toHaveLength(1)
  })
  it('rejects missing arrays, duplicate identities and inconsistent counts', () => {
    expect(() => parseLegionellaHealth({ ...alerts(), errors: undefined })).toThrow('malformed')
    const duplicate = alerts()
    duplicate.source_channels[1] = duplicate.source_channels[0]
    expect(() => parseLegionellaHealth(duplicate)).toThrow('duplicated')
    expect(() => parseLegionellaHealth({ ...alerts(), items: [] })).toThrow('disagree')
  })
  it('does not treat a snapshot without retrieval proof as retrieved', () => {
    const value = alerts()
    value.source_channels[0].content_sha256 = ''
    expect(legionellaChannelRows(parseLegionellaHealth(value))[0].retrieved).toBe(false)
  })
  it('rejects unsafe source links', () => {
    expect(safeSourceUrl('javascript:alert(1)')).toBeNull()
    expect(safeSourceUrl('https://www.nyc.gov/')).toBe('https://www.nyc.gov/')
  })
})
