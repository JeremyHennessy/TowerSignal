import type { jsPDF } from 'jspdf'
import type { ChangeEvent } from '../types/history'
import type { SourceMetadata, SystemDetail, SystemSummary } from '../types/data'
import { formatDate, formatTimestamp, signalLabel } from '../domain/labels'

type PdfDoc = jsPDF

interface ClientPdfInput {
  row: SystemSummary
  detail: SystemDetail
  historyEvents: ChangeEvent[]
}

interface PdfContext {
  doc: PdfDoc
  row: SystemSummary
  detail: SystemDetail
  historyEvents: ChangeEvent[]
  y: number
  sectionTitle: string
}

interface InfoCard {
  label: string
  value: string
  detail?: string
  tone?: 'default' | 'attention' | 'positive'
}

const PAGE_WIDTH = 612
const MARGIN = 48
const CONTENT_WIDTH = PAGE_WIDTH - (MARGIN * 2)
const BODY_TOP = 76
const BODY_BOTTOM = 738
const GAP = 12

const BRAND = [20, 63, 55] as const
const BRAND_SOFT = [231, 241, 237] as const
const ACCENT = [40, 103, 87] as const
const INK = [30, 39, 36] as const
const MUTED = [92, 106, 101] as const
const LINE = [216, 225, 221] as const
const PALE = [247, 249, 248] as const
const ATTENTION = [161, 96, 24] as const
const ATTENTION_BG = [255, 247, 232] as const
const POSITIVE = [38, 99, 80] as const
const POSITIVE_BG = [237, 248, 243] as const

const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function ascii(value: unknown): string {
  return String(value ?? '')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201c\u201d]/g, '"')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\u2192/g, ' to ')
    .replace(/\u2022/g, '-')
    .replace(/\u00a0/g, ' ')
    .replace(/[^\u0020-\u007E]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function display(value: unknown, fallback = 'Not published'): string {
  const text = ascii(value)
  return text || fallback
}

function date(value: string | null | undefined): string {
  return value ? ascii(formatDate(value)) : 'Not published'
}

function timestamp(value: string | null | undefined): string {
  return value ? ascii(formatTimestamp(value)) : 'Not published'
}

function money(value: number | null | undefined): string {
  return value == null ? 'Not published' : currency.format(value)
}

function number(value: number | null | undefined): string {
  return value == null ? 'Not published' : integer.format(value)
}

function safeFilename(value: string): string {
  return ascii(value)
    .replace(/[^A-Za-z0-9._-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 90)
}

function wrap(doc: PdfDoc, text: string, width: number): string[] {
  return doc.splitTextToSize(ascii(text), Math.max(36, width)) as string[]
}

function setText(doc: PdfDoc, size: number, color: readonly [number, number, number] = INK, weight: 'normal' | 'bold' = 'normal') {
  doc.setFont('helvetica', weight)
  doc.setFontSize(size)
  doc.setTextColor(...color)
}

function setFill(doc: PdfDoc, color: readonly [number, number, number]) {
  doc.setFillColor(color[0], color[1], color[2])
}

function setDraw(doc: PdfDoc, color: readonly [number, number, number]) {
  doc.setDrawColor(color[0], color[1], color[2])
}

function drawBodyHeader(ctx: PdfContext) {
  const { doc } = ctx
  doc.setFillColor(...BRAND)
  doc.rect(0, 0, PAGE_WIDTH, 10, 'F')
  setText(doc, 9, BRAND, 'bold')
  doc.text('TowerSignal', MARGIN, 40)
  setText(doc, 8, MUTED)
  doc.text(ascii(ctx.sectionTitle), PAGE_WIDTH - MARGIN, 40, { align: 'right' })
  doc.setDrawColor(...LINE)
  doc.setLineWidth(0.7)
  doc.line(MARGIN, 52, PAGE_WIDTH - MARGIN, 52)
}

function addPage(ctx: PdfContext, sectionTitle = ctx.sectionTitle) {
  ctx.doc.addPage('letter', 'portrait')
  ctx.sectionTitle = sectionTitle
  ctx.y = BODY_TOP
  drawBodyHeader(ctx)
}

function ensureSpace(ctx: PdfContext, required: number, sectionTitle = ctx.sectionTitle) {
  if (ctx.y + required <= BODY_BOTTOM) return
  addPage(ctx, sectionTitle)
}

function sectionHeading(ctx: PdfContext, title: string, subtitle?: string) {
  const { doc } = ctx
  ensureSpace(ctx, subtitle ? 70 : 52)
  ctx.y += 8
  setText(doc, 17, BRAND, 'bold')
  doc.text(ascii(title), MARGIN, ctx.y)
  ctx.y += 9
  doc.setDrawColor(...BRAND_SOFT)
  doc.setLineWidth(3)
  doc.line(MARGIN, ctx.y, MARGIN + 52, ctx.y)
  ctx.y += 17
  if (subtitle) {
    setText(doc, 9.4, MUTED)
    const lines = wrap(doc, subtitle, CONTENT_WIDTH)
    doc.text(lines, MARGIN, ctx.y)
    ctx.y += lines.length * 12 + 8
  }
}

function callout(ctx: PdfContext, title: string, body: string, tone: 'default' | 'attention' | 'positive' = 'default') {
  const { doc } = ctx
  const bg = tone === 'attention' ? ATTENTION_BG : tone === 'positive' ? POSITIVE_BG : BRAND_SOFT
  const fg = tone === 'attention' ? ATTENTION : tone === 'positive' ? POSITIVE : BRAND
  setText(doc, 10.5, fg, 'bold')
  const titleLines = wrap(doc, title, CONTENT_WIDTH - 28)
  setText(doc, 9.2, INK)
  const bodyLines = wrap(doc, body, CONTENT_WIDTH - 28)
  const height = 20 + titleLines.length * 12 + bodyLines.length * 11.5
  ensureSpace(ctx, height + 10)
  setFill(doc, bg)
  setDraw(doc, fg)
  doc.roundedRect(MARGIN, ctx.y, CONTENT_WIDTH, height, 6, 6, 'FD')
  setText(doc, 10.5, fg, 'bold')
  doc.text(titleLines, MARGIN + 14, ctx.y + 18)
  setText(doc, 9.2, INK)
  doc.text(bodyLines, MARGIN + 14, ctx.y + 18 + titleLines.length * 12 + 5)
  ctx.y += height + 18
}

function infoCards(ctx: PdfContext, cards: InfoCard[], columns = 2) {
  const { doc } = ctx
  const width = (CONTENT_WIDTH - GAP * (columns - 1)) / columns
  for (let i = 0; i < cards.length; i += columns) {
    const group = cards.slice(i, i + columns)
    const metrics = group.map(card => {
      setText(doc, 8, MUTED, 'bold')
      const labelLines = wrap(doc, card.label.toUpperCase(), width - 22)
      setText(doc, 12.2, INK, 'bold')
      const valueLines = wrap(doc, card.value, width - 22)
      setText(doc, 8.5, MUTED)
      const detailLines = card.detail ? wrap(doc, card.detail, width - 22) : []
      const h = 20 + labelLines.length * 9 + valueLines.length * 14 + detailLines.length * 10 + 13
      return { card, labelLines, valueLines, detailLines, h: Math.max(68, h) }
    })
    const height = Math.max(...metrics.map(item => item.h))
    ensureSpace(ctx, height + GAP)
    metrics.forEach((item, index) => {
      const x = MARGIN + index * (width + GAP)
      const toneColor = item.card.tone === 'attention' ? ATTENTION : item.card.tone === 'positive' ? POSITIVE : BRAND
      const toneBg = item.card.tone === 'attention' ? ATTENTION_BG : item.card.tone === 'positive' ? POSITIVE_BG : PALE
      setFill(doc, toneBg)
      doc.setDrawColor(...LINE)
      doc.roundedRect(x, ctx.y, width, height, 5, 5, 'FD')
      setText(doc, 7.8, toneColor, 'bold')
      doc.text(item.labelLines, x + 11, ctx.y + 15)
      setText(doc, 11.8, INK, 'bold')
      const valueY = ctx.y + 20 + item.labelLines.length * 9
      doc.text(item.valueLines, x + 11, valueY)
      if (item.detailLines.length) {
        setText(doc, 8.2, MUTED)
        doc.text(item.detailLines, x + 11, valueY + item.valueLines.length * 13 + 5)
      }
    })
    ctx.y += height + GAP
  }
}

function bullets(ctx: PdfContext, items: string[]) {
  const { doc } = ctx
  for (const item of items) {
    setText(doc, 9.2, INK)
    const lines = wrap(doc, item, CONTENT_WIDTH - 18)
    const height = Math.max(14, lines.length * 11.5)
    ensureSpace(ctx, height + 3)
    setText(doc, 10, BRAND, 'bold')
    doc.text('-', MARGIN, ctx.y)
    setText(doc, 9.2, INK)
    doc.text(lines, MARGIN + 14, ctx.y)
    ctx.y += height + 3
  }
  ctx.y += 4
}

function table(
  ctx: PdfContext,
  headers: string[],
  rows: string[][],
  widths: number[],
  emptyMessage: string,
) {
  const { doc } = ctx
  if (!rows.length) {
    callout(ctx, 'No attached records', emptyMessage)
    return
  }

  const drawHeader = () => {
    doc.setFillColor(...BRAND_SOFT)
    doc.setDrawColor(...LINE)
    doc.rect(MARGIN, ctx.y, CONTENT_WIDTH, 24, 'FD')
    let x = MARGIN
    headers.forEach((header, index) => {
      setText(doc, 7.4, BRAND, 'bold')
      doc.text(ascii(header).toUpperCase(), x + 6, ctx.y + 15)
      x += widths[index]
    })
    ctx.y += 24
  }

  ensureSpace(ctx, 52)
  drawHeader()

  rows.forEach((row, rowIndex) => {
    const wrapped = row.map((cell, index) => {
      setText(doc, 8.1, INK)
      return wrap(doc, cell, widths[index] - 12)
    })
    const rowHeight = Math.max(25, Math.max(...wrapped.map(lines => lines.length)) * 10 + 10)
    if (ctx.y + rowHeight > BODY_BOTTOM) {
      addPage(ctx, ctx.sectionTitle)
      drawHeader()
    }
    setFill(doc, rowIndex % 2 === 0 ? [255, 255, 255] : PALE)
    doc.setDrawColor(...LINE)
    doc.rect(MARGIN, ctx.y, CONTENT_WIDTH, rowHeight, 'FD')
    let x = MARGIN
    wrapped.forEach((lines, index) => {
      setText(doc, 8.1, INK)
      doc.text(lines, x + 6, ctx.y + 13)
      x += widths[index]
    })
    ctx.y += rowHeight
  })
  ctx.y += 10
}

function sourceEntry(ctx: PdfContext, source: SourceMetadata) {
  const { doc } = ctx
  setText(doc, 9.4, INK, 'bold')
  const nameLines = wrap(doc, source.name, CONTENT_WIDTH - 28)
  const meta = [
    source.dataset_id,
    `${integer.format(source.source_record_count)} source rows`,
    source.matched_record_count != null ? `${integer.format(source.matched_record_count)} exact-matched records` : '',
  ].filter(Boolean).join(' | ')
  const timing = [
    `Retrieved ${timestamp(source.retrieved_at)}`,
    source.source_last_updated_at ? `Source updated ${timestamp(source.source_last_updated_at)}` : '',
  ].filter(Boolean).join(' | ')
  const scopeLines = source.source_query_scope ? wrap(doc, source.source_query_scope, CONTENT_WIDTH - 28) : []
  const height = 43 + nameLines.length * 11 + scopeLines.length * 10
  ensureSpace(ctx, height + 8)
  doc.setFillColor(...PALE)
  doc.setDrawColor(...LINE)
  doc.roundedRect(MARGIN, ctx.y, CONTENT_WIDTH, height, 5, 5, 'FD')
  setText(doc, 9.4, INK, 'bold')
  doc.text(nameLines, MARGIN + 12, ctx.y + 16)
  setText(doc, 7.8, MUTED)
  const metaY = ctx.y + 18 + nameLines.length * 11
  doc.text(ascii(meta), MARGIN + 12, metaY)
  doc.text(ascii(timing), MARGIN + 12, metaY + 11)
  if (scopeLines.length) {
    setText(doc, 7.6, MUTED)
    doc.text(scopeLines, MARGIN + 12, metaY + 22)
  }
  if (source.url) {
    setText(doc, 7.8, ACCENT, 'bold')
    doc.textWithLink('Open official source', PAGE_WIDTH - MARGIN - 12, ctx.y + 16, { url: source.url, align: 'right' })
  }
  ctx.y += height + 8
}

function inspectionViolations(detail: SystemDetail) {
  return [...detail.inspection_history]
    .sort((a, b) => (b.inspection_date ?? '').localeCompare(a.inspection_date ?? ''))
    .flatMap(inspection => inspection.violations.map(violation => ({ inspection, violation })))
}

function primaryObservation(row: SystemSummary, detail: SystemDetail) {
  const recent = detail.signals.find(signal => signal.type === 'CONFIRMED_RECENT_VIOLATION')
  if (row.recent_confirmed_violation && recent) {
    return {
      title: 'Recent NYC Health violation evidence is attached',
      body: `${recent.date ? `${date(recent.date)} - ` : ''}${display(recent.reason)} This is a public-record observation, not a current compliance determination.`,
      tone: 'attention' as const,
    }
  }
  const clientSignals = detail.signals.filter(item => item.fact_class !== 'COMMERCIAL_SIGNAL')
  const signal = clientSignals.find(item => item.type === row.primary_signal) ?? clientSignals[0]
  if (signal) {
    return {
      title: display(signal.title, signalLabel(row.primary_signal)),
      body: `${signal.date ? `${date(signal.date)} - ` : ''}${display(signal.reason)}`,
      tone: signal.evidence_confidence === 'CONFIRMED' ? 'positive' as const : 'default' as const,
    }
  }
  return {
    title: 'No current compliance or event observation is attached',
    body: 'The report still includes site identity, source coverage and available historical public records. Absence of an attached current observation does not establish absence of a site condition.',
    tone: 'default' as const,
  }
}

function drawCover(ctx: PdfContext) {
  const { doc, row, detail } = ctx
  doc.setFillColor(...BRAND)
  doc.rect(0, 0, PAGE_WIDTH, 202, 'F')

  doc.setFillColor(223, 238, 233)
  doc.roundedRect(MARGIN, 38, 44, 44, 8, 8, 'F')
  setText(doc, 18, BRAND, 'bold')
  doc.text('TS', MARGIN + 22, 66, { align: 'center' })

  setText(doc, 11, [220, 235, 231], 'bold')
  doc.text('TOWERSIGNAL', MARGIN + 58, 55)
  setText(doc, 8.5, [187, 211, 204])
  doc.text('SOURCE-BACKED SITE INTELLIGENCE', MARGIN + 58, 71)

  setText(doc, 25, [255, 255, 255], 'bold')
  doc.text('Site Intelligence Report', MARGIN, 122)
  setText(doc, 16, [228, 239, 236], 'bold')
  const addressLines = wrap(doc, display(row.address, `System ${row.system_id}`), CONTENT_WIDTH)
  doc.text(addressLines.slice(0, 2), MARGIN, 151)
  setText(doc, 9.5, [187, 211, 204])
  doc.text(ascii(`${display(row.borough, '')}${row.zip ? ` ${row.zip}` : ''} | Cooling Tower System ${row.system_id}`), MARGIN, 187)

  ctx.y = 235
  const observation = primaryObservation(row, detail)
  callout(ctx, observation.title, observation.body, observation.tone)

  infoCards(ctx, [
    {
      label: 'Registered equipment',
      value: `${row.active_equipment.toLocaleString()} active unit${row.active_equipment === 1 ? '' : 's'}`,
      detail: `${(detail.planimetric_building_tower_features?.length ?? 0).toLocaleString()} mapped tower footprint${(detail.planimetric_building_tower_features?.length ?? 0) === 1 ? '' : 's'}`,
    },
    {
      label: 'Latest public sample',
      value: date(detail.sample_history.latest_sample_date),
      detail: detail.sample_history.latest_sample_interval_days != null ? `${detail.sample_history.latest_sample_interval_days.toLocaleString()} days since prior reported sample` : `${detail.sample_history.sample_count.toLocaleString()} reported sample date${detail.sample_history.sample_count === 1 ? '' : 's'}`,
    },
    {
      label: 'NYC Health inspections',
      value: detail.inspection_history.length.toLocaleString(),
      detail: `${inspectionViolations(detail).length.toLocaleString()} attached violation citation${inspectionViolations(detail).length === 1 ? '' : 's'}`,
    },
    {
      label: 'Data snapshot',
      value: display(detail.metadata.snapshot_date),
      detail: `Generated ${timestamp(detail.metadata.generated_at)}`,
    },
  ])

  ctx.y += 2
  sectionHeading(ctx, 'Report identifiers')
  infoCards(ctx, [
    { label: 'System ID', value: row.system_id },
    { label: 'Evidence confidence', value: row.evidence_confidence.replaceAll('_', ' ') },
    { label: 'BIN', value: display(detail.identity.bin) },
    { label: 'BBL', value: display(detail.identity.bbl) },
  ])

  callout(
    ctx,
    'Use and interpretation',
    'This report summarizes source-backed public records and exact-key property joins. It does not establish current operating status, maintenance history, service responsibility, safety, legal compliance or causation. Verify current site conditions and authoritative agency status before relying on any observation.',
  )
}

function drawOverview(ctx: PdfContext) {
  addPage(ctx, 'Executive overview')
  sectionHeading(ctx, 'Executive overview', 'A concise client-facing view of the public-record evidence currently attached to this site.')

  const history = ctx.detail.historical_profile
  const oathCases = ctx.detail.oath_case_history ?? []
  infoCards(ctx, [
    { label: 'Registered cooling-tower units', value: ctx.row.active_equipment.toLocaleString(), detail: 'NYC registration record' },
    { label: 'Mapped physical tower features', value: (ctx.detail.planimetric_building_tower_features?.length ?? 0).toLocaleString(), detail: `NYC planimetric imagery ${ctx.detail.metadata.planimetric_imagery_year ?? 2022}` },
    { label: 'Latest public sample', value: date(ctx.detail.sample_history.latest_sample_date), detail: `${ctx.detail.sample_history.sample_count.toLocaleString()} reported sample date${ctx.detail.sample_history.sample_count === 1 ? '' : 's'}` },
    { label: 'Latest NYC Health inspection', value: date(ctx.row.latest_inspection_date), detail: ctx.row.latest_inspection_type ? display(ctx.row.latest_inspection_type) : 'Inspection type not published' },
    { label: 'Inspection history', value: `${history?.inspection.inspection_count ?? ctx.detail.inspection_history.length} inspection${(history?.inspection.inspection_count ?? ctx.detail.inspection_history.length) === 1 ? '' : 's'}`, detail: `${history?.inspection.violation_citation_count ?? inspectionViolations(ctx.detail).length} violation citation${(history?.inspection.violation_citation_count ?? inspectionViolations(ctx.detail).length) === 1 ? '' : 's'}` },
    { label: 'Exact-matched OATH cases', value: oathCases.length.toLocaleString(), detail: history ? `${money(history.oath.balance_due_total)} published balance due` : 'Lifecycle data shown when exact summons match exists' },
  ])

  sectionHeading(ctx, 'Current public-record observations')
  const clientSignals = ctx.detail.signals.filter(signal => signal.fact_class !== 'COMMERCIAL_SIGNAL')
  if (clientSignals.length) {
    bullets(ctx, clientSignals.slice(0, 8).map(signal => {
      const prefix = signal.date ? `${date(signal.date)} - ` : ''
      return `${display(signal.title)} [${signal.evidence_confidence.replaceAll('_', ' ')}]: ${prefix}${display(signal.reason)}`
    }))
  } else {
    callout(ctx, 'No current TowerSignal signal', 'No current priority signal was generated from the attached source data. Historical and site-context evidence remains included below.')
  }

  sectionHeading(ctx, 'Property and physical context')
  const building = ctx.detail.building_context
  infoCards(ctx, [
    { label: 'PLUTO owner', value: display(building?.owner_name), detail: ctx.detail.identity.bbl ? `Exact BBL ${ctx.detail.identity.bbl}` : 'No exact property identity attached' },
    { label: 'Building area', value: building?.building_area_sqft != null ? `${number(building.building_area_sqft)} sq ft` : 'Not published', detail: building?.floors != null ? `${number(building.floors)} floors` : undefined },
    { label: 'Building class', value: display(building?.building_class), detail: building?.land_use ? `Land use ${display(building.land_use)}` : undefined },
    { label: 'Year built', value: building?.year_built ? String(building.year_built) : 'Not published', detail: `${(ctx.detail.building_footprints?.length ?? 0).toLocaleString()} exact-BIN building footprint${(ctx.detail.building_footprints?.length ?? 0) === 1 ? '' : 's'}` },
  ])

  callout(
    ctx,
    'Evidence boundary',
    'A source non-match is reported as a non-match, not as proof that the underlying owner, project, condition, service relationship or compliance state does not exist. Property records are joined only through the exact source identifiers represented in TowerSignal.',
  )
}

function drawSiteContext(ctx: PdfContext) {
  addPage(ctx, 'Site and building context')
  sectionHeading(ctx, 'Site identity and asset context', 'Public identifiers, registered equipment and exact-key building evidence attached to this cooling-tower system.')

  table(ctx,
    ['Field', 'Published value'],
    [
      ['Site address', display(ctx.row.address)],
      ['Borough / ZIP', `${display(ctx.row.borough)} / ${display(ctx.row.zip)}`],
      ['Cooling tower system ID', ctx.row.system_id],
      ['BIN', display(ctx.detail.identity.bin)],
      ['BBL', display(ctx.detail.identity.bbl)],
      ['Registered active equipment', ctx.row.active_equipment.toLocaleString()],
      ['Coordinates', ctx.detail.identity.coordinate_status === 'VALID' && ctx.detail.identity.latitude != null && ctx.detail.identity.longitude != null ? `${ctx.detail.identity.latitude.toFixed(5)}, ${ctx.detail.identity.longitude.toFixed(5)}` : 'Not published / unusable'],
    ],
    [160, 356],
    'Site identity fields are unavailable in the current generated record.',
  )

  sectionHeading(ctx, 'Physical evidence')
  const towers = ctx.detail.planimetric_building_tower_features ?? []
  const footprints = ctx.detail.building_footprints ?? []
  const roofCount = towers.filter(item => item.sub_feature_code === '212000').length
  const groundCount = towers.filter(item => item.sub_feature_code === '212010').length
  const maxRoof = footprints.reduce<number | null>((max, item) => item.height_roof_ft == null ? max : Math.max(max ?? item.height_roof_ft, item.height_roof_ft), null)
  infoCards(ctx, [
    { label: 'Mapped tower footprints', value: towers.length.toLocaleString(), detail: `${roofCount} roof-level | ${groundCount} ground-level` },
    { label: 'Building footprints', value: footprints.length.toLocaleString(), detail: maxRoof != null ? `Published roof height up to ${number(maxRoof)} ft` : 'No published roof-height value' },
    { label: 'Registered vs mapped', value: `${ctx.row.active_equipment} registered / ${towers.length} mapped`, detail: ctx.row.active_equipment === towers.length ? 'Counts align in current records' : 'Count difference is a field-verification cue, not a defect finding', tone: ctx.row.active_equipment === towers.length ? 'positive' : 'attention' },
    { label: 'Planimetric vintage', value: String(ctx.detail.metadata.planimetric_imagery_year ?? 2022), detail: 'Physical map evidence may not reflect later configuration changes' },
  ])

  sectionHeading(ctx, 'Building and infrastructure')
  const building = ctx.detail.building_context
  table(ctx,
    ['Attribute', 'Public record'],
    [
      ['PLUTO owner', display(building?.owner_name)],
      ['Building class', display(building?.building_class)],
      ['Land use', display(building?.land_use)],
      ['Year built', building?.year_built ? String(building.year_built) : 'Not published'],
      ['Building area', building?.building_area_sqft != null ? `${number(building.building_area_sqft)} sq ft` : 'Not published'],
      ['Lot area', building?.lot_area_sqft != null ? `${number(building.lot_area_sqft)} sq ft` : 'Not published'],
      ['Floors', number(building?.floors)],
      ['Total units', number(building?.total_units)],
    ],
    [180, 336],
    'No exact-BBL PLUTO building context is attached to this system.',
  )

  const lead = ctx.detail.nyc_lead_service_lines
  const water = ctx.detail.nyc_building_water_signals
  const cms = ctx.detail.cms_institutional_context
  const historicalWater = ctx.detail.nyc_historical_water_context
  const leadMaterials = lead ? Object.entries(lead.summary.material_counts).filter(([, count]) => count > 0).map(([material, count]) => `${material}${count > 1 ? ` x${count}` : ''}`).join(', ') : ''
  infoCards(ctx, [
    { label: 'NYC DEP service-line records', value: lead ? lead.summary.record_count.toLocaleString() : '0', detail: leadMaterials || 'No exact-BBL material record attached' },
    { label: 'Building-water signals', value: water ? water.summary.record_count.toLocaleString() : '0', detail: water?.summary.latest_observation_date ? `Latest observation ${date(water.summary.latest_observation_date)}` : 'No exact BBL/BIN signal attached' },
    { label: 'Institutional facility context', value: cms ? cms.facilities.length.toLocaleString() : '0', detail: cms?.facilities[0]?.facility_name ? display(cms.facilities[0].facility_name) : 'No attached CMS facility context' },
    { label: 'Historical water requests', value: historicalWater ? historicalWater.summary.request_count.toLocaleString() : '0', detail: historicalWater?.summary.first_reported_date ? `${date(historicalWater.summary.first_reported_date)} to ${date(historicalWater.summary.latest_reported_date)}` : 'No exact-BBL historical request context' },
  ])
}

function drawCompliance(ctx: PdfContext) {
  ctx.sectionTitle = 'Sampling, inspections and enforcement'
  ensureSpace(ctx, 210, ctx.sectionTitle)
  sectionHeading(ctx, 'Sampling history', 'Reported public sample dates are shown as observations. Intervals do not establish continuous operation or retroactive noncompliance.')

  const samples = [...ctx.detail.sample_history.dates].sort((a, b) => b.localeCompare(a))
  const sampleRows = samples.slice(0, 14).map((sample, index) => {
    const previous = samples[index + 1]
    const interval = previous ? Math.round((new Date(`${sample}T00:00:00`).getTime() - new Date(`${previous}T00:00:00`).getTime()) / 86400000) : null
    return [date(sample), interval == null ? 'Oldest shown record' : `${interval} days since prior reported sample`]
  })
  table(ctx, ['Reported sample date', 'Interval context'], sampleRows, [170, 346], 'No usable public sample history is attached.')

  sectionHeading(ctx, 'NYC Health inspection history')
  const inspections = [...ctx.detail.inspection_history].sort((a, b) => (b.inspection_date ?? '').localeCompare(a.inspection_date ?? ''))
  table(ctx,
    ['Date', 'Inspection type', 'Violations'],
    inspections.slice(0, 12).map(item => [date(item.inspection_date), display(item.inspection_type), item.violation_count.toLocaleString()]),
    [105, 321, 90],
    'No published NYC Health inspection history is attached to this system.',
  )

  sectionHeading(ctx, 'Violation citation detail')
  const violations = inspectionViolations(ctx.detail)
  if (violations.length) {
    violations.slice(0, 10).forEach(({ inspection, violation }, index) => {
      const title = `${date(inspection.inspection_date)} - ${display(violation.violation_type, 'Violation')}${violation.violation_code ? ` [${display(violation.violation_code)}]` : ''}`
      const body = [
        violation.violation_text ?? violation.citation_text ?? 'No published violation description.',
        violation.law_section ? `Law section: ${violation.law_section}` : '',
        violation.summons_number ? `Summons: ${violation.summons_number}` : '',
      ].filter(Boolean).join(' | ')
      callout(ctx, `${index + 1}. ${title}`, body, 'attention')
    })
  } else {
    callout(ctx, 'No attached violation citation detail', 'No violation/citation values are attached to the current joined NYC Health inspection history.')
  }

  sectionHeading(ctx, 'OATH case lifecycle')
  const oath = [...(ctx.detail.oath_case_history ?? [])].sort((a, b) => (b.violation_date ?? '').localeCompare(a.violation_date ?? ''))
  table(ctx,
    ['Ticket', 'Violation date', 'Outcome / status', 'Penalty / balance'],
    oath.slice(0, 10).map(item => [
      item.ticket_number,
      date(item.violation_date),
      `${display(item.hearing_result, display(item.hearing_status))}${item.compliance_status ? ` | ${display(item.compliance_status)}` : ''}`,
      `${money(item.penalty_imposed)} / ${money(item.balance_due)}`,
    ]),
    [84, 92, 218, 122],
    'No OATH case was exact-matched to this system\'s published NYC Health summons numbers.',
  )

  if (ctx.detail.historical_profile) {
    sectionHeading(ctx, 'Historical profile')
    const profile = ctx.detail.historical_profile
    infoCards(ctx, [
      { label: 'Registration date', value: date(profile.registration_date), detail: profile.registration_age_days != null ? `${Math.floor(profile.registration_age_days / 365)} years of registration history` : undefined },
      { label: 'First public evidence', value: date(profile.first_public_evidence_date) },
      { label: 'Reported sample range', value: profile.sample.first_reported_date ? `${date(profile.sample.first_reported_date)} to ${date(profile.sample.latest_reported_date)}` : 'Not published', detail: `${profile.sample.reported_sample_count} reported dates` },
      { label: 'Inspection range', value: profile.inspection.first_inspection_date ? `${date(profile.inspection.first_inspection_date)} to ${date(profile.inspection.latest_inspection_date)}` : 'Not published', detail: `${profile.inspection.inspections_with_violations} inspection${profile.inspection.inspections_with_violations === 1 ? '' : 's'} with violation evidence` },
    ])
  }
}

function drawProjects(ctx: PdfContext) {
  ctx.sectionTitle = 'Projects and observed changes'
  ensureSpace(ctx, 190, ctx.sectionTitle)
  sectionHeading(ctx, 'DOB NOW project activity', 'Exact-BBL project filings provide property timing context. Only explicit published wording is treated as cooling-tower project evidence.')

  const jobs = [...(ctx.detail.dob_activity_history ?? [])].sort((a, b) => (b.activity_date ?? '').localeCompare(a.activity_date ?? ''))
  table(ctx,
    ['Activity', 'Filing', 'Published description', 'Status'],
    jobs.slice(0, 10).map(job => [
      date(job.activity_date),
      display(job.job_filing_number),
      display(job.job_description, 'No description published'),
      `${display(job.filing_status)} | ${job.explicit_cooling_tower_mention ? 'Cooling tower explicit' : job.mechanical_systems || job.boiler_equipment ? 'Mechanical / boiler context' : 'Property project'}`,
    ]),
    [88, 92, 238, 98],
    'No exact-BBL DOB NOW project activity is attached to this system.',
  )

  sectionHeading(ctx, 'Building-water and institutional context')
  const water = ctx.detail.nyc_building_water_signals
  if (water) {
    infoCards(ctx, [
      { label: 'Exact property water records', value: water.summary.record_count.toLocaleString(), detail: water.summary.latest_observation_date ? `Latest ${date(water.summary.latest_observation_date)}` : undefined },
      { label: '311 building-water signals', value: water.summary.water_311_building_signal_count.toLocaleString() },
      { label: 'HPD open water violations', value: water.summary.hpd_open_water_violation_count.toLocaleString() },
      { label: 'DOB water filings / permits', value: `${water.summary.dob_water_job_filing_count} / ${water.summary.dob_water_permit_count}` },
    ])
  } else {
    callout(ctx, 'No exact property building-water signal set', 'No exact-BBL/BIN 311, HPD, DOB or LL84 building-water signal is attached to this system.')
  }

  const cms = ctx.detail.cms_institutional_context
  if (cms?.facilities.length) {
    table(ctx,
      ['Facility', 'Type', 'Ownership', 'Identity basis'],
      cms.facilities.slice(0, 8).map(item => [
        display(item.facility_name),
        display(item.facility_type, item.source_kind),
        display(item.ownership_type),
        item.property_link_confidence.replaceAll('_', ' '),
      ]),
      [188, 110, 116, 102],
      'No institutional facility records are attached.',
    )
  }

  sectionHeading(ctx, 'TowerSignal observation history', 'These timestamps represent when TowerSignal detected a difference between preserved source snapshots; they are not necessarily the date of the underlying real-world event.')
  const events = [...ctx.historyEvents].sort((a, b) => b.detected_at.localeCompare(a.detected_at))
  table(ctx,
    ['Detected', 'Observed change', 'Source observation', 'Source'],
    events.slice(0, 12).map(event => [
      timestamp(event.detected_at),
      event.event_type.replaceAll('_', ' '),
      event.source_observation_date ? date(event.source_observation_date) : 'Not published',
      display(event.source),
    ]),
    [118, 170, 108, 120],
    'No TowerSignal changes have been observed for this system in the attached preserved history.',
  )
}

function drawSources(ctx: PdfContext) {
  addPage(ctx, 'Sources and methodology')
  sectionHeading(ctx, 'Sources and provenance', `${ctx.detail.metadata.sources.length.toLocaleString()} source dataset${ctx.detail.metadata.sources.length === 1 ? '' : 's'} are represented in this generated detail record. Each entry retains its dataset identity and retrieval timing.`)

  ctx.detail.metadata.sources.forEach(source => sourceEntry(ctx, source))

  sectionHeading(ctx, 'Methodology and evidence boundaries')
  bullets(ctx, [
    'Cooling-tower system identity is retained from the source registration record. Property and physical context is attached only through the exact source identifiers supported by each dataset.',
    'OATH lifecycle evidence is matched by exact NYC Health summons number to OATH ticket identity. A payment or case outcome does not establish physical remediation.',
    'PLUTO, DOB and HPD property context is exact-BBL based. Planimetric cooling-tower and building-footprint evidence is exact-BIN based.',
    'Historical sample intervals and observed changes are descriptive public-record history. They do not establish continuous equipment operation, retroactive noncompliance or causation.',
    'A source non-match is not converted into a negative factual claim. It means only that TowerSignal did not attach an exact matching public record under the current source contract.',
  ])

  callout(
    ctx,
    'Client-use notice',
    'TowerSignal is an intelligence and research product. This report is not legal, engineering, environmental, medical or regulatory advice. Confirm current site conditions and authoritative agency status before making operational, compliance, procurement or service decisions.',
    'default',
  )
}

function addFooters(doc: PdfDoc, row: SystemSummary, detail: SystemDetail) {
  const pageCount = doc.getNumberOfPages()
  for (let page = 1; page <= pageCount; page += 1) {
    doc.setPage(page)
    doc.setDrawColor(...LINE)
    doc.setLineWidth(0.5)
    doc.line(MARGIN, 758, PAGE_WIDTH - MARGIN, 758)
    setText(doc, 7.3, MUTED)
    doc.text(ascii(`TowerSignal | Site Intelligence Report | System ${row.system_id} | Data generated ${timestamp(detail.metadata.generated_at)}`), MARGIN, 773)
    doc.text(`${page} / ${pageCount}`, PAGE_WIDTH - MARGIN, 773, { align: 'right' })
  }
}

export async function exportAccountClientPdf({ row, detail, historyEvents }: ClientPdfInput): Promise<void> {
  const { jsPDF: JsPdf } = await import('jspdf')
  const doc = new JsPdf({
    orientation: 'portrait',
    unit: 'pt',
    format: 'letter',
    compress: true,
    putOnlyUsedFonts: true,
  })

  doc.setProperties({
    title: ascii(`TowerSignal Site Intelligence Report - ${display(row.address, row.system_id)}`),
    subject: 'Source-backed cooling-tower and building-water site intelligence',
    author: 'TowerSignal',
    creator: 'TowerSignal',
    keywords: 'TowerSignal, cooling tower, building water, site intelligence, public records',
  })

  const ctx: PdfContext = {
    doc,
    row,
    detail,
    historyEvents,
    y: BODY_TOP,
    sectionTitle: 'Site Intelligence Report',
  }

  drawCover(ctx)
  drawOverview(ctx)
  drawSiteContext(ctx)
  drawCompliance(ctx)
  drawProjects(ctx)
  drawSources(ctx)
  addFooters(doc, row, detail)

  const exportDate = new Date().toISOString().slice(0, 10)
  const site = safeFilename(row.address ?? row.system_id) || row.system_id
  const filename = `TowerSignal_${site}_${row.system_id}_Site_Intelligence_${exportDate}.pdf`
  doc.save(filename)
}
