import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import type { TorontoProperty } from '../types/toronto'

export function TorontoMarketMap({ properties, selectedId, onSelect }: { properties: TorontoProperty[]; selectedId: string | null; onSelect: (property: TorontoProperty) => void }) {
  const container = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null)
  const markerRef = useRef(new Map<string, L.Marker>())

  useEffect(() => {
    if (!container.current || mapRef.current) return
    const map = L.map(container.current, { zoomControl: true }).setView([43.6532, -79.3832], 11)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map)
    const cluster = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 44 })
    cluster.addTo(map)
    mapRef.current = map
    clusterRef.current = cluster
    return () => { map.remove(); mapRef.current = null; clusterRef.current = null }
  }, [])

  useEffect(() => {
    const cluster = clusterRef.current
    if (!cluster) return
    cluster.clearLayers()
    markerRef.current.clear()
    for (const property of properties) {
      const confirmed = property.tower_evidence_status === 'CONFIRMED_DOCUMENTARY_TOWER'
      const review = property.tower_evidence_status !== 'NO_TOWER_ASSERTION' && !confirmed
      const marker = L.marker([property.latitude, property.longitude], {
        icon: L.divIcon({ className: 'tower-marker-wrap', html: `<span class="tower-marker${confirmed ? ' violation' : review ? ' caution' : ''}"></span>`, iconSize: [16, 16], iconAnchor: [8, 8] }),
        title: property.display_address,
      })
      marker.on('click', () => onSelect(property))
      marker.bindTooltip(`${property.display_address} · ${property.tower_evidence_status.replaceAll('_', ' ').toLowerCase()}`)
      cluster.addLayer(marker)
      markerRef.current.set(property.property_id, marker)
    }
  }, [properties, onSelect])

  useEffect(() => {
    if (!selectedId || !mapRef.current) return
    const marker = markerRef.current.get(selectedId)
    if (marker) mapRef.current.setView(marker.getLatLng(), Math.max(mapRef.current.getZoom(), 15), { animate: true })
  }, [selectedId])

  return <div className="toronto-map-shell"><div ref={container} className="toronto-map" role="region" aria-label="Toronto canonical property map" /><div className="map-meta">{properties.length.toLocaleString()} mapped canonical properties · clustered</div></div>
}
