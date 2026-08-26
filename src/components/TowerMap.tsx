import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import type { SystemSummary } from '../types/data'

export function TowerMap({ systems, selectedId, onSelect }: { systems: SystemSummary[]; selectedId: string | null; onSelect: (row: SystemSummary) => void }) {
  const container = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null)
  const markerRef = useRef(new Map<string, L.Marker>())

  useEffect(() => {
    if (!container.current || mapRef.current) return
    const map = L.map(container.current, { zoomControl: true }).setView([40.7128, -74.006], 10)
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
    cluster.clearLayers(); markerRef.current.clear()
    for (const system of systems) {
      if (system.latitude == null || system.longitude == null) continue
      const marker = L.marker([system.latitude, system.longitude], {
        icon: L.divIcon({ className: 'tower-marker-wrap', html: `<span class="tower-marker${system.recent_confirmed_violation ? ' violation' : system.signal_types.includes('POTENTIAL_SAMPLING_GAP') ? ' caution' : ''}"></span>`, iconSize: [16,16], iconAnchor: [8,8] }),
        title: system.address ?? system.system_id,
      })
      marker.on('click', () => onSelect(system))
      marker.bindTooltip(`${system.address ?? system.system_id} · score ${system.priority_score}`)
      cluster.addLayer(marker); markerRef.current.set(system.system_id, marker)
    }
  }, [systems, onSelect])

  useEffect(() => {
    if (!selectedId || !mapRef.current) return
    const marker = markerRef.current.get(selectedId)
    if (marker) mapRef.current.setView(marker.getLatLng(), Math.max(mapRef.current.getZoom(), 14), { animate: true })
  }, [selectedId])

  return <div className="map-shell"><div ref={container} className="map" role="region" aria-label="Filtered NYC cooling tower map" /><div className="map-meta">{systems.filter(s => s.latitude != null && s.longitude != null).length.toLocaleString()} mapped records · clustered</div></div>
}
