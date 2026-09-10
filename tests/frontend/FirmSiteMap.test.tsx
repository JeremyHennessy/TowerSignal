import { act, render } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import type { KnownFirmSiteRelationship } from '../../src/types/firm'
import { FirmSiteMap } from '../../src/components/FirmSiteMap'

const leaflet = vi.hoisted(() => {
  const map = { setView: vi.fn().mockReturnThis(), fitBounds: vi.fn(), getZoom: vi.fn(() => 14), remove: vi.fn() }
  const cluster = { addTo: vi.fn(), addLayer: vi.fn(), clearLayers: vi.fn(), zoomToShowLayer: vi.fn((_marker, callback: () => void) => callback()) }
  const markers: Array<{ bindTooltip: ReturnType<typeof vi.fn>; on: ReturnType<typeof vi.fn>; getLatLng: ReturnType<typeof vi.fn>; handlers: Record<string, () => void> }> = []
  return { map, cluster, markers }
})

vi.mock('leaflet', () => ({ default: {
  map: vi.fn(() => leaflet.map),
  tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
  markerClusterGroup: vi.fn(() => leaflet.cluster),
  divIcon: vi.fn(value => value),
  latLngBounds: vi.fn(value => value),
  marker: vi.fn(latLng => {
    const handlers: Record<string, () => void> = {}
    const marker = { bindTooltip: vi.fn(), on: vi.fn((event: string, callback: () => void) => { handlers[event] = callback }), getLatLng: vi.fn(() => latLng), handlers }
    leaflet.markers.push(marker)
    return marker
  }),
} }))
vi.mock('leaflet.markercluster', () => ({}))

const site: KnownFirmSiteRelationship = {
  site_id: 'NYC-BIN-100001', address: '10 ALPHA ST', latitude: 40.75, longitude: -73.99,
  system_ids: ['SYS-1'], roles: ['DWT_INSPECTION_PROVIDER'], relationship_classes: ['OBSERVED_SERVICE'],
  evidence_classes: ['DWT_INSPECTION_BY_FIRM_OBSERVED_SERVICE'], source_record_ids: ['DWT-1'],
  observation_count: 1, serviced: true, contracted: false, project_role: false, tower_account_count: 1, mapped: true,
}

beforeEach(() => { vi.clearAllMocks(); leaflet.markers.length = 0 })

test('selecting a site retains marker layers and uses the latest selection callback', () => {
  const first = vi.fn()
  const second = vi.fn()
  const view = render(<FirmSiteMap sites={[site]} selectedSiteId={null} onSelect={first} />)
  expect(leaflet.cluster.clearLayers).toHaveBeenCalledTimes(1)
  const marker = leaflet.markers[0]
  view.rerender(<FirmSiteMap sites={[site]} selectedSiteId={site.site_id} onSelect={second} />)
  expect(leaflet.cluster.clearLayers).toHaveBeenCalledTimes(1)
  expect(leaflet.markers).toHaveLength(1)
  expect(leaflet.cluster.zoomToShowLayer).toHaveBeenCalledWith(marker, expect.any(Function))
  act(() => marker.handlers.click())
  expect(second).toHaveBeenCalledWith(site)
  expect(first).not.toHaveBeenCalled()
})

test('changing the actual filtered sites rebuilds the map and removes old markers', () => {
  const onSelect = vi.fn()
  const view = render(<FirmSiteMap sites={[site]} selectedSiteId={null} onSelect={onSelect} />)
  const other = { ...site, site_id: 'NYC-BIN-100002', address: '20 ALPHA ST' }
  view.rerender(<FirmSiteMap sites={[other]} selectedSiteId={null} onSelect={onSelect} />)
  expect(leaflet.cluster.clearLayers).toHaveBeenCalledTimes(2)
  expect(leaflet.markers).toHaveLength(2)
  act(() => leaflet.markers[1].handlers.click())
  expect(onSelect).toHaveBeenCalledWith(other)
  view.rerender(<FirmSiteMap sites={[]} selectedSiteId={null} onSelect={onSelect} />)
  expect(leaflet.cluster.clearLayers).toHaveBeenCalledTimes(3)
})
