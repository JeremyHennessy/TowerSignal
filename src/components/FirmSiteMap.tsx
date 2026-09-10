import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import type { KnownFirmSiteRelationship } from '../types/firm'

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  })[character] ?? character)
}

function markerClass(site: KnownFirmSiteRelationship): string {
  if (site.serviced) return 'firm-site-marker serviced'
  if (site.contracted) return 'firm-site-marker contracted'
  return 'firm-site-marker related'
}

export function FirmSiteMap({
  sites,
  selectedSiteId,
  onSelect,
}: {
  sites: KnownFirmSiteRelationship[]
  selectedSiteId: string | null
  onSelect: (site: KnownFirmSiteRelationship) => void
}) {
  const container = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null)
  const markerRef = useRef(new Map<string, L.Marker>())
  const renderedSites = useRef<KnownFirmSiteRelationship[] | null>(null)
  const selectRef = useRef(onSelect)

  useEffect(() => {
    if (!container.current || mapRef.current) return
    const markerMap = markerRef.current
    const map = L.map(container.current, { zoomControl: true }).setView([40.7128, -74.006], 10)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)
    const cluster = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 42 })
    cluster.addTo(map)
    mapRef.current = map
    clusterRef.current = cluster
    return () => {
      map.remove()
      mapRef.current = null
      clusterRef.current = null
      markerMap.clear()
      renderedSites.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const cluster = clusterRef.current
    if (!map || !cluster) return
    selectRef.current = onSelect
    // Selecting a site re-renders the parent with a new array and callback.
    // Retain the existing marker layers when their source records are unchanged;
    // rebuilding here races the selected-site zoom and detaches clicked markers.
    if (renderedSites.current?.length === sites.length
      && sites.every((site, index) => renderedSites.current?.[index] === site)) return
    renderedSites.current = sites
    cluster.clearLayers()
    markerRef.current.clear()
    const bounds: L.LatLngExpression[] = []
    for (const site of sites) {
      if (site.latitude == null || site.longitude == null) continue
      const latLng: L.LatLngExpression = [site.latitude, site.longitude]
      bounds.push(latLng)
      const marker = L.marker(latLng, {
        icon: L.divIcon({
          className: 'firm-site-marker-wrap',
          html: `<span class="${markerClass(site)}"></span>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
        title: site.address ?? site.site_id,
      })
      const relationship = site.serviced ? 'Observed service' : site.contracted ? 'Confirmed contract link' : 'Related evidence'
      marker.bindTooltip(`${escapeHtml(site.address ?? site.site_id)} · ${escapeHtml(relationship)}`)
      marker.on('click', () => selectRef.current(site))
      cluster.addLayer(marker)
      markerRef.current.set(site.site_id, marker)
    }
    if (bounds.length === 1) map.setView(bounds[0], 14)
    if (bounds.length > 1) map.fitBounds(L.latLngBounds(bounds), { padding: [28, 28], maxZoom: 14 })
  }, [sites, onSelect])

  useEffect(() => {
    if (!selectedSiteId || !mapRef.current) return
    const marker = markerRef.current.get(selectedSiteId)
    if (!marker) return
    const cluster = clusterRef.current
    if (cluster) cluster.zoomToShowLayer(marker, () => mapRef.current?.setView(marker.getLatLng(), Math.max(mapRef.current?.getZoom() ?? 12, 14)))
  }, [selectedSiteId])

  const mapped = sites.filter(site => site.latitude != null && site.longitude != null).length
  return <div className="map-shell firm-site-map-shell">
    <div ref={container} className="map firm-site-map" role="region" aria-label="Known firm site relationship map" />
    <div className="map-meta">{mapped.toLocaleString()} mapped of {sites.length.toLocaleString()} related sites · <span className="firm-map-key serviced">observed service</span> · <span className="firm-map-key contracted">confirmed contract</span> · <span className="firm-map-key related">other role</span></div>
  </div>
}
