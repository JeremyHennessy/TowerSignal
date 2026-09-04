import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Feature, MultiPolygon, Polygon } from 'geojson'
import type { PlanimetricBuildingTowerFeature, SystemDetail } from '../types/data'

const SOURCE_URL = 'https://data.cityofnewyork.us/City-Government/NYC-Planimetric-Database-Cooling-Towers/x748-37q7'

function featureLabel(index: number) {
  return `Mapped tower footprint ${index + 1}`
}

export function PlanimetricTowerSection({ detail }: { detail: SystemDetail }) {
  const container = useRef<HTMLDivElement | null>(null)
  const features = detail.planimetric_building_tower_features
  const featureCount = features?.length ?? 0

  useEffect(() => {
    if (!container.current || !features?.length) return

    const map = L.map(container.current, {
      zoomControl: true,
      attributionControl: true,
      scrollWheelZoom: false,
    })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)

    const bounds = L.latLngBounds([])
    features.forEach((feature, index) => {
      const geoJsonFeature: Feature<Polygon | MultiPolygon> = {
        type: 'Feature',
        properties: {},
        geometry: feature.geometry,
      }
      const layer = L.geoJSON(geoJsonFeature, {
        style: {
          color: '#153f38',
          weight: 3,
          opacity: 0.95,
          fillColor: '#245e52',
          fillOpacity: 0.32,
        },
      }).addTo(map)
      layer.bindTooltip(featureLabel(index))
      bounds.extend(layer.getBounds())
    })

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [28, 28], maxZoom: 20 })
    }

    return () => {
      map.remove()
    }
  }, [features])

  return <section className="planimetric-section">
    <h3>Physical tower location</h3>
    {featureCount === 0 ? <>
      <div className="empty-inline">No NYC Planimetric cooling-tower feature was exact-matched to this system's published BIN.</div>
      <p className="microcopy">A missing 2022 Planimetric feature is not evidence that the registered cooling tower does not physically exist. The physical-map source and current regulatory registry have different observation and update regimes.</p>
    </> : <>
      <div className="planimetric-summary">
        <strong>{featureCount} mapped cooling-tower feature{featureCount === 1 ? '' : 's'} on BIN {detail.identity.bin}</strong>
        <span>Exact BIN attachment · 2022 aerial-derived physical observation</span>
      </div>
      <div className="planimetric-map-shell">
        <div ref={container} className="planimetric-map" role="region" aria-label={`Mapped physical cooling-tower features on BIN ${detail.identity.bin ?? 'unknown'}`} />
      </div>
      <div className="planimetric-feature-list">
        {features?.map((feature, index) => <article className="planimetric-feature" key={feature.global_id}>
          <div className="planimetric-feature-head"><strong>{featureLabel(index)}</strong><span>BIN {feature.bin}</span></div>
          <dl className="identity-grid">
            <div><dt>Global ID</dt><dd className="mono planimetric-id">{feature.global_id}</dd></div>
            <div><dt>Source ID</dt><dd>{feature.source_id ?? '—'}</dd></div>
            <div><dt>Feature code</dt><dd>{feature.feature_code ?? '—'}</dd></div>
            <div><dt>Sub-feature code</dt><dd>{feature.sub_feature_code ?? '—'}</dd></div>
            <div><dt>Source status</dt><dd>{feature.status ?? '—'}</dd></div>
            <div><dt>Observation imagery</dt><dd>{feature.imagery_year}</dd></div>
          </dl>
        </article>)}
      </div>
      <p className="microcopy">NYC Planimetric cooling-tower geometry is attached only by exact BIN and is building-level physical context. It does not establish which mapped polygon corresponds to this specific registered System ID when a building has multiple systems, and it does not prove the current equipment configuration or operating status. GlobalID is used as the feature identity because the current source has duplicate SOURCE_ID values; SOURCE_ID remains visible provenance. Published feature and sub-feature codes are retained without guessing their numeric domain labels.</p>
      <a className="planimetric-source-link" href={SOURCE_URL} target="_blank" rel="noreferrer">Open NYC Planimetric source ↗</a>
    </>}
  </section>
}
