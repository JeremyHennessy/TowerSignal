import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import type { NysSystem } from '../types/nys'

function markerClass(system: NysSystem): string {
  if (system.regulation_compliance === 'Non-compliant' || system.ct_status === 'Disinfection Required') return ' nys-attention'
  if (system.ct_status === 'Decommissioned' || system.ct_status === 'Out of Service') return ' nys-inactive'
  if (system.ct_status === 'Sample_Required' || system.ct_status === 'Update_Required' || system.ct_status === 'Missing Legionella Result') return ' nys-caution'
  return ''
}

export function NysTowerMap({ systems, selectedId, onSelect }: { systems: NysSystem[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const container = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null)
  const markerRef = useRef(new Map<string, L.Marker>())

  useEffect(() => {
    if (!container.current || mapRef.current) return
    const map = L.map(container.current, { zoomControl: true }).setView([42.9, -75.5], 6)
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
        icon: L.divIcon({ className: 'tower-marker-wrap', html: `<span class="tower-marker${markerClass(system)}"></span>`, iconSize: [16,16], iconAnchor: [8,8] }),
        title: system.address ?? system.system_id,
      })
      marker.on('click', () => onSelect(system.system_id))
      marker.bindTooltip(`${system.address ?? system.system_id} · ${system.regulation_compliance ?? 'Compliance not published'} · ${system.ct_status ?? 'Status not published'}`)
      cluster.addLayer(marker); markerRef.current.set(system.system_id, marker)
    }
  }, [systems, onSelect])

  useEffect(() => {
    if (!selectedId || !mapRef.current) return
    const marker = markerRef.current.get(selectedId)
    if (marker) mapRef.current.setView(marker.getLatLng(), Math.max(mapRef.current.getZoom(), 14), { animate: true })
  }, [selectedId])

  return <div className="map-shell"><div ref={container} className="map" role="region" aria-label="Filtered New York State cooling tower registry map" /><div className="map-meta">{systems.filter(s => s.latitude != null && s.longitude != null).length.toLocaleString()} mapped NYS equipment records · clustered</div></div>
}