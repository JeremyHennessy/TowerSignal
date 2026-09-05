import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Feature, MultiPolygon, Polygon } from 'geojson'
import type { SystemDetail } from '../types/data'

const PLANIMETRIC_SOURCE_URL = 'https://data.cityofnewyork.us/City-Government/NYC-Planimetric-Database-Cooling-Towers/x748-37q7'
const PLANIMETRIC_DOMAIN_URL = 'https://services6.arcgis.com/yG5s3afENB5iO9fj/ArcGIS/rest/services/Cooling_Towers_2022/FeatureServer/3'
const BUILDING_SOURCE_URL = 'https://data.cityofnewyork.us/City-Government/BUILDING/5zhs-2jue'
const ORTHO_SOURCE_URL = 'https://gis.ny.gov/2022-orthoimagery'
const ORTHO_TILE_URL = 'https://orthos.its.ny.gov/arcgis/rest/services/wms/2022/MapServer/tile/{z}/{y}/{x}'
const COLLAPSE_TOWER_DETAILS_AT = 12

function featureLabel(index: number) {
  return `Mapped tower footprint ${index + 1}`
}

function footprintLabel(index: number) {
  return `Building outline ${index + 1}`
}

function locationLevelLabel(code: string | null) {
  if (code === '212000') return 'Roof level'
  if (code === '212010') return 'Ground level'
  return 'Unresolved source code'
}

function formatFeet(value: number | null) {
  return value == null ? '—' : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ft`
}

export function PlanimetricTowerSection({ detail }: { detail: SystemDetail }) {
  const container = useRef<HTMLDivElement | null>(null)
  const features = detail.planimetric_building_tower_features
  const buildingFootprints = detail.building_footprints
  const featureCount = features?.length ?? 0
  const footprintCount = buildingFootprints?.length ?? 0
  const roofLevelCount = features?.filter(feature => feature.sub_feature_code === '212000').length ?? 0
  const groundLevelCount = features?.filter(feature => feature.sub_feature_code === '212010').length ?? 0
  const hasRoofMapContext = featureCount > 0 || footprintCount > 0

  useEffect(() => {
    if (!container.current || !hasRoofMapContext) return

    const map = L.map(container.current, {
      zoomControl: true,
      attributionControl: true,
      scrollWheelZoom: false,
      maxZoom: 20,
    })

    const ortho = L.tileLayer(ORTHO_TILE_URL, {
      minZoom: 0,
      maxNativeZoom: 19,
      maxZoom: 20,
      attribution: '2022 orthoimagery © NYS ITS Geospatial Services',
    }).addTo(map)
    const street = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
      attribution: '&copy; OpenStreetMap contributors',
    })
    L.control.layers({
      '2022 NYS aerial': ortho,
      'Street map': street,
    }, undefined, { position: 'topright' }).addTo(map)
    L.control.scale({ imperial: true, metric: true, position: 'bottomleft' }).addTo(map)

    const bounds = L.latLngBounds([])

    buildingFootprints?.forEach((footprint, index) => {
      const geoJsonFeature: Feature<Polygon | MultiPolygon> = {
        type: 'Feature',
        properties: {},
        geometry: footprint.geometry,
      }
      const shadow = L.geoJSON(geoJsonFeature, {
        style: {
          color: '#111827',
          weight: 6,
          opacity: 0.62,
          fillOpacity: 0,
        },
      }).addTo(map)
      const outline = L.geoJSON(geoJsonFeature, {
        style: {
          color: '#ffffff',
          weight: 3,
          opacity: 0.98,
          dashArray: '8 5',
          fillOpacity: 0.02,
        },
      }).addTo(map)
      outline.bindTooltip(footprintLabel(index))
      bounds.extend(shadow.getBounds())
    })

    features?.forEach((feature, index) => {
      const geoJsonFeature: Feature<Polygon | MultiPolygon> = {
        type: 'Feature',
        properties: {},
        geometry: feature.geometry,
      }
      const layer = L.geoJSON(geoJsonFeature, {
        style: {
          color: '#f59e0b',
          weight: 3,
          opacity: 1,
          fillColor: '#f59e0b',
          fillOpacity: 0.38,
          dashArray: feature.sub_feature_code === '212010' ? '7 5' : undefined,
        },
      }).addTo(map)
      layer.bindTooltip(`${featureLabel(index)} · ${locationLevelLabel(feature.sub_feature_code)}`)
      bounds.extend(layer.getBounds())
    })

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [34, 34], maxZoom: 20 })
    }

    return () => {
      map.remove()
    }
  }, [buildingFootprints, features, hasRoofMapContext])

  const featureCards = features?.map((feature, index) => <article className="planimetric-feature" key={feature.global_id}>
    <div className="planimetric-feature-head"><strong>{featureLabel(index)}</strong><span>BIN {feature.bin}</span></div>
    <dl className="identity-grid">
      <div><dt>Structure location</dt><dd><strong>{locationLevelLabel(feature.sub_feature_code)}</strong></dd></div>
      <div><dt>Source sub-feature code</dt><dd>{feature.sub_feature_code ?? '—'}</dd></div>
      <div><dt>Global ID</dt><dd className="mono planimetric-id">{feature.global_id}</dd></div>
      <div><dt>Source ID</dt><dd>{feature.source_id ?? '—'}</dd></div>
      <div><dt>Feature code</dt><dd>{feature.feature_code ?? '—'}</dd></div>
      <div><dt>Source status</dt><dd>{feature.status ?? '—'}</dd></div>
      <div><dt>Observation imagery</dt><dd>{feature.imagery_year}</dd></div>
    </dl>
  </article>)

  return <section className="planimetric-section">
    <h3>Physical tower location</h3>
    <div className="planimetric-summary">
      <strong>{featureCount} mapped cooling-tower footprint{featureCount === 1 ? '' : 's'} · {footprintCount} building outline{footprintCount === 1 ? '' : 's'}</strong>
      <span>Exact BIN attachment · tower observation and aerial imagery: 2022 · building footprint: current NYC layer</span>
      {featureCount > 0 && <span>{roofLevelCount} roof level · {groundLevelCount} ground level · classification is source-coded by NYC OTI</span>}
    </div>

    {hasRoofMapContext && <>
      <div className="planimetric-map-shell">
        <div ref={container} className="planimetric-map" role="region" aria-label={`Aerial roof map with cooling-tower and building footprints on BIN ${detail.identity.bin ?? 'unknown'}`} />
      </div>
      <div className="roof-map-legend" aria-label="Roof map legend">
        <span><i className="roof-legend-tower" />Cooling-tower footprint</span>
        <span><i className="roof-legend-building" />Current building outline</span>
        <span className="roof-legend-imagery">2022 NYS orthophoto</span>
      </div>
    </>}

    {featureCount === 0 ? <>
      <div className="empty-inline">No NYC Planimetric cooling-tower feature was exact-matched to this system's published BIN.</div>
      <p className="microcopy">A missing 2022 Planimetric feature is not evidence that the registered cooling tower does not physically exist. Where a current building footprint is available, the aerial roof context remains visible for field verification.</p>
    </> : featureCount > COLLAPSE_TOWER_DETAILS_AT ? <details className="roof-tower-details">
      <summary>Tower feature evidence · {featureCount} mapped footprints</summary>
      <div className="planimetric-feature-list">{featureCards}</div>
    </details> : <div className="planimetric-feature-list">{featureCards}</div>}

    {footprintCount > 0 && <details className="roof-building-details">
      <summary>Building footprint context · {footprintCount} exact-BIN feature{footprintCount === 1 ? '' : 's'}</summary>
      <div className="planimetric-feature-list">
        {buildingFootprints?.map((footprint, index) => <article className="planimetric-feature" key={footprint.doitt_id ? `doitt-${footprint.doitt_id}` : `object-${footprint.object_id}`}>
          <div className="planimetric-feature-head"><strong>{footprintLabel(index)}</strong><span>BIN {footprint.bin}</span></div>
          <dl className="identity-grid">
            <div><dt>DOITT ID</dt><dd>{footprint.doitt_id ?? '—'}</dd></div>
            <div><dt>Roof height</dt><dd>{formatFeet(footprint.height_roof_ft)}</dd></div>
            <div><dt>Ground elevation</dt><dd>{formatFeet(footprint.ground_elevation_ft)}</dd></div>
            <div><dt>Construction year</dt><dd>{footprint.construction_year ?? '—'}</dd></div>
            <div><dt>Geometry source</dt><dd>{footprint.geometry_source ?? '—'}</dd></div>
            <div><dt>Footprint status</dt><dd>{footprint.last_status_type ?? '—'}</dd></div>
          </dl>
        </article>)}
      </div>
    </details>}

    <p className="microcopy">The orange tower polygons are NYC Planimetric physical observations derived from 2022 aerial imagery and are attached only by exact BIN. NYC OTI's coded domain defines sub-feature 212000 as Roof Level and 212010 as Ground Level; TowerSignal preserves that source classification rather than inferring location from imagery. The dashed building outline comes from NYC OTI's current building-footprint layer and can therefore reflect edits made after the 2022 imagery. Neither layer establishes which polygon corresponds to a specific System ID when multiple registered systems share a building, nor do they prove current equipment configuration or operating status.</p>
    <div className="roof-source-links">
      <a className="planimetric-source-link" href={PLANIMETRIC_SOURCE_URL} target="_blank" rel="noreferrer">Tower polygons ↗</a>
      <a className="planimetric-source-link" href={PLANIMETRIC_DOMAIN_URL} target="_blank" rel="noreferrer">Roof/ground code domain ↗</a>
      <a className="planimetric-source-link" href={BUILDING_SOURCE_URL} target="_blank" rel="noreferrer">Building footprints ↗</a>
      <a className="planimetric-source-link" href={ORTHO_SOURCE_URL} target="_blank" rel="noreferrer">2022 NYS orthophoto ↗</a>
    </div>
  </section>
}
