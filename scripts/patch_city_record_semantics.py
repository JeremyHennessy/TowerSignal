from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {path}, found {count}: {old[:160]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# City Record source semantics.
replace_once(
    "scripts/towersignal/city_record.py",
    "from dataclasses import dataclass\nfrom datetime import date, timedelta\n",
    "from dataclasses import dataclass\nfrom datetime import date, timedelta\nfrom html import unescape\n",
)
replace_once(
    "scripts/towersignal/city_record.py",
    "from .procurement import classify_procurement, normalize_notice, normalize_space, procurement_source_health, utc_now\n",
    "from .procurement import classify_procurement, normalize_notice, normalize_space, parse_iso_date, procurement_source_health, utc_now\n",
)
replace_once(
    "scripts/towersignal/city_record.py",
    '''    open_where = (\n        "type_of_notice_description = 'Solicitation' "\n        f"AND due_date >= '{_floating_timestamp(as_of)}'"\n    )\n    award_start = as_of - timedelta(days=award_lookback_days)\n    awards_where = (\n        "type_of_notice_description = 'Award' "\n        f"AND start_date >= '{_floating_timestamp(award_start)}'"\n    )\n    return (("OPEN_SOLICITATIONS", open_where), ("RECENT_AWARDS", awards_where))\n''',
    '''    sentinel_start = date(2099, 1, 1)\n    open_where = (\n        "type_of_notice_description = 'Solicitation' "\n        f"AND due_date >= '{_floating_timestamp(as_of)}' "\n        f"AND due_date < '{_floating_timestamp(sentinel_start)}'"\n    )\n    unverified_deadline_where = (\n        "type_of_notice_description = 'Solicitation' "\n        f"AND due_date >= '{_floating_timestamp(sentinel_start)}'"\n    )\n    award_start = as_of - timedelta(days=award_lookback_days)\n    awards_where = (\n        "type_of_notice_description = 'Award' "\n        f"AND start_date >= '{_floating_timestamp(award_start)}'"\n    )\n    return (\n        ("OPEN_SOLICITATIONS", open_where),\n        ("UNVERIFIED_DEADLINE_SOLICITATIONS", unverified_deadline_where),\n        ("RECENT_AWARDS", awards_where),\n    )\n''',
)
replace_once(
    "scripts/towersignal/city_record.py",
    '''def source_document_url(value: Any) -> str | None:\n    if isinstance(value, Mapping):\n        return normalize_space(str(value.get("url") or value.get("href") or "")) or None\n    return normalize_space(str(value or "")) or None\n\n\ndef normalize_city_record_row''',
    '''def source_document_urls(value: Any) -> tuple[str, ...]:\n    if isinstance(value, Mapping):\n        text = str(value.get("url") or value.get("href") or "")\n    else:\n        text = str(value or "")\n    urls: list[str] = []\n    for candidate in text.split(","):\n        normalized = normalize_space(unescape(candidate))\n        if normalized and normalized not in urls:\n            urls.append(normalized)\n    return tuple(urls)\n\n\ndef source_document_url(value: Any) -> str | None:\n    urls = source_document_urls(value)\n    return urls[0] if urls else None\n\n\ndef deadline_semantics(value: Any) -> tuple[str | None, str, str | None]:\n    parsed = parse_iso_date(value)\n    if parsed is None:\n        return None, "MISSING", None\n    if int(parsed[:4]) >= 2099:\n        return None, "UNVERIFIED_SENTINEL", parsed\n    return parsed, "VERIFIED_DATE", parsed\n\n\ndef normalize_city_record_row''',
)
replace_once(
    "scripts/towersignal/city_record.py",
    '''    notice_type = normalize_space(str(row.get("type_of_notice_description") or "")) or None\n    text = source_text(row)\n    notice = normalize_notice(\n''',
    '''    notice_type = normalize_space(str(row.get("type_of_notice_description") or "")) or None\n    text = source_text(row)\n    due_date, due_date_status, source_due_date = deadline_semantics(row.get("due_date"))\n    source_urls = source_document_urls(row.get("document_links"))\n    if scope == "RECENT_AWARDS":\n        normalized_status = "AWARDED"\n    elif due_date_status == "UNVERIFIED_SENTINEL":\n        normalized_status = "DEADLINE_UNVERIFIED"\n    elif scope == "OPEN_SOLICITATIONS":\n        normalized_status = "OPEN"\n    else:\n        normalized_status = None\n    notice = normalize_notice(\n''',
)
replace_once(
    "scripts/towersignal/city_record.py",
    '''        due_date=row.get("due_date"),\n        notice_start_date=row.get("start_date"),\n        notice_end_date=row.get("end_date"),\n''',
    '''        due_date=due_date,\n        notice_start_date=row.get("start_date"),\n        notice_end_date=row.get("end_date"),\n''',
)
replace_once(
    "scripts/towersignal/city_record.py",
    '''        status="OPEN" if scope == "OPEN_SOLICITATIONS" else "AWARDED" if scope == "RECENT_AWARDS" else None,\n        source_url=source_document_url(row.get("document_links")) or DATASET_PAGE,\n''',
    '''        status=normalized_status,\n        source_url=(source_urls[0] if source_urls else DATASET_PAGE),\n''',
)
replace_once(
    "scripts/towersignal/city_record.py",
    '''            "scope": scope,\n            "vendor_raw": normalize_space(str(row.get("vendor_name") or "")) or None,\n''',
    '''            "scope": scope,\n            "due_date_raw": normalize_space(str(row.get("due_date") or "")) or None,\n            "due_date_status": due_date_status,\n            "source_due_date": source_due_date,\n            "source_urls": list(source_urls),\n            "vendor_raw": normalize_space(str(row.get("vendor_name") or "")) or None,\n''',
)
replace_once(
    "scripts/towersignal/city_record.py",
    '''            "open_relevant_opportunities": sum(1 for item in normalized if item.get("scope") == "OPEN_SOLICITATIONS"),\n            "recent_relevant_awards": len(relevant_awards),\n''',
    '''            "open_relevant_opportunities": sum(1 for item in normalized if item.get("status") == "OPEN"),\n            "unverified_deadline_opportunities": sum(1 for item in normalized if item.get("status") == "DEADLINE_UNVERIFIED"),\n            "recent_relevant_awards": len(relevant_awards),\n''',
)

# Type contract.
replace_once(
    "src/types/procurement.ts",
    '''  due_date?: string | null\n  notice_start_date?: string | null\n''',
    '''  due_date?: string | null\n  due_date_raw?: string | null\n  due_date_status?: 'VERIFIED_DATE' | 'UNVERIFIED_SENTINEL' | 'MISSING' | null\n  source_due_date?: string | null\n  notice_start_date?: string | null\n''',
)
replace_once(
    "src/types/procurement.ts",
    '''  source_url?: string | null\n  retrieved_at: string\n''',
    '''  source_url?: string | null\n  source_urls?: string[]\n  retrieved_at: string\n''',
)
replace_once(
    "src/types/procurement.ts",
    '''  summary: { scoped_record_count: number; relevant_record_count: number; open_relevant_opportunities: number; recent_relevant_awards: number; unresolved_vendor_count: number; classification_counts: Record<string, number> }\n''',
    '''  summary: { scoped_record_count: number; relevant_record_count: number; open_relevant_opportunities: number; unverified_deadline_opportunities: number; recent_relevant_awards: number; unresolved_vendor_count: number; classification_counts: Record<string, number> }\n''',
)

# Opportunities UI: explicit deadline semantics and document list.
replace_once(
    "src/components/OpportunitiesPage.tsx",
    '''        <article><span className="reference-metric-icon urgent">↗</span><div><small>Open solicitations</small><strong>{number.format(procurement.cityRecord.summary.open_relevant_opportunities)}</strong><span>Relevant City Record notices</span></div></article>\n        <article><span className="reference-metric-icon warning">◷</span><div><small>Recent awards</small><strong>{number.format(procurement.cityRecord.summary.recent_relevant_awards)}</strong><span>City Record lookback window</span></div></article>\n''',
    '''        <article><span className="reference-metric-icon urgent">↗</span><div><small>Open solicitations</small><strong>{number.format(procurement.cityRecord.summary.open_relevant_opportunities)}</strong><span>Verified future City Record deadlines</span></div></article>\n        <article><span className="reference-metric-icon warning">?</span><div><small>Unverified deadlines</small><strong>{number.format(procurement.cityRecord.summary.unverified_deadline_opportunities)}</strong><span>Sentinel / indefinite source dates</span></div></article>\n        <article><span className="reference-metric-icon warning">◷</span><div><small>Recent awards</small><strong>{number.format(procurement.cityRecord.summary.recent_relevant_awards)}</strong><span>City Record lookback window</span></div></article>\n''',
)
replace_once(
    "src/components/OpportunitiesPage.tsx",
    '''          <td>{procurementDate(row) ? formatDate(procurementDate(row) ?? '') : '—'}<small>{row.due_date ? 'due date' : row.start_date ? 'contract start' : row.award_date ? 'award date' : 'source date'}</small></td>\n          <td>{row.source_url ? <a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}<small>{row.facility_match_confidence ?? row.tower_link_confidence ?? 'UNLINKED'} facility/account</small></td>\n''',
    '''          <td>{row.due_date_status === 'UNVERIFIED_SENTINEL' ? <><strong>Deadline unverified</strong><small>Source value {row.due_date_raw?.slice(0, 10) ?? 'sentinel / indefinite'}</small></> : <>{procurementDate(row) ? formatDate(procurementDate(row) ?? '') : '—'}<small>{row.due_date ? 'due date' : row.start_date ? 'contract start' : row.award_date ? 'award date' : 'source date'}</small></>}</td>\n          <td>{(row.source_urls?.length ?? 0) > 1 ? <details><summary>{row.source_urls?.length} source documents</summary><div className="workflow-toolbox-list">{row.source_urls?.map((url, index) => <a key={url} className="table-link" href={url} target="_blank" rel="noreferrer">Document {index + 1} ↗</a>)}</div></details> : row.source_url ? <a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}<small>{row.facility_match_confidence ?? row.tower_link_confidence ?? 'UNLINKED'} facility/account</small></td>\n''',
)
replace_once(
    "src/components/OpportunitiesPage.tsx",
    '''Priority remains WHY NOW for cooling-tower accounts. Procurement classifications and observed contract values are separate source-backed commercial evidence and do not change Priority Score 1.0.''',
    '''Priority remains WHY NOW for cooling-tower accounts. Procurement classifications and observed contract values are separate source-backed commercial evidence and do not change Priority Score 1.1.''',
)

# Python regression tests.
replace_once(
    "tests/python/test_city_record.py",
    '''    normalize_city_record_row,\n)\n''',
    '''    normalize_city_record_row,\n    source_document_urls,\n)\n''',
)
replace_once(
    "tests/python/test_city_record.py",
    '''        self.assertIn("due_date >= '2026-08-26T00:00:00.000'", scopes["OPEN_SOLICITATIONS"])\n        self.assertIn("type_of_notice_description = 'Award'", scopes["RECENT_AWARDS"])\n''',
    '''        self.assertIn("due_date >= '2026-08-26T00:00:00.000'", scopes["OPEN_SOLICITATIONS"])\n        self.assertIn("due_date < '2099-01-01T00:00:00.000'", scopes["OPEN_SOLICITATIONS"])\n        self.assertIn("due_date >= '2099-01-01T00:00:00.000'", scopes["UNVERIFIED_DEADLINE_SOLICITATIONS"])\n        self.assertIn("type_of_notice_description = 'Award'", scopes["RECENT_AWARDS"])\n''',
)
replace_once(
    "tests/python/test_city_record.py",
    '''    def test_build_payload_classifies_after_complete_scoped_retrieval(self):\n''',
    '''    def test_sentinel_deadline_is_preserved_but_not_normalized_as_open(self):\n        source = row(20240411118, "HVAC efficiency cooling tower project", due="9999-09-09T16:00:00.000")\n        item = normalize_city_record_row(source, retrieved_at="2026-09-16T19:00:00Z", scope="UNVERIFIED_DEADLINE_SOLICITATIONS")\n        self.assertIsNone(item["due_date"])\n        self.assertEqual(item["due_date_raw"], "9999-09-09T16:00:00.000")\n        self.assertEqual(item["source_due_date"], "9999-09-09")\n        self.assertEqual(item["due_date_status"], "UNVERIFIED_SENTINEL")\n        self.assertEqual(item["status"], "DEADLINE_UNVERIFIED")\n        self.assertEqual(item["raw"]["due_date"], "9999-09-09T16:00:00.000")\n\n    def test_2099_source_date_is_treated_as_unverified_sentinel(self):\n        source = row(20170329022, "MECHANICAL CONSTRUCTION WORK", due="2099-12-31T14:00:00.000")\n        source["printout_1"] = "MECHANICAL CONSTRUCTION WORK - Due 12-31-99 at 2:00 P.M."\n        item = normalize_city_record_row(source, retrieved_at="2026-09-16T19:00:00Z", scope="UNVERIFIED_DEADLINE_SOLICITATIONS")\n        self.assertIsNone(item["due_date"])\n        self.assertEqual(item["source_due_date"], "2099-12-31")\n        self.assertEqual(item["due_date_status"], "UNVERIFIED_SENTINEL")\n        self.assertEqual(item["status"], "DEADLINE_UNVERIFIED")\n\n    def test_multi_document_field_is_split_unescaped_and_deduplicated(self):\n        raw = {"url": "https://a856-cityrecord.nyc.gov/Search/GetFile?SectionID=6&amp;DocumentID=30888,https://a856-cityrecord.nyc.gov/Search/GetFile?SectionID=6&amp;DocumentID=30889,https://a856-cityrecord.nyc.gov/Search/GetFile?SectionID=6&amp;DocumentID=30888"}\n        urls = source_document_urls(raw)\n        self.assertEqual(len(urls), 2)\n        self.assertEqual(urls[0], "https://a856-cityrecord.nyc.gov/Search/GetFile?SectionID=6&DocumentID=30888")\n        self.assertEqual(urls[1], "https://a856-cityrecord.nyc.gov/Search/GetFile?SectionID=6&DocumentID=30889")\n\n    def test_build_payload_classifies_after_complete_scoped_retrieval(self):\n''',
)
replace_once(
    "tests/python/test_city_record.py",
    '''        self.assertEqual(summary["open_relevant_opportunities"], 2)\n        self.assertEqual(summary["recent_relevant_awards"], 1)\n''',
    '''        self.assertEqual(summary["open_relevant_opportunities"], 2)\n        self.assertEqual(summary["unverified_deadline_opportunities"], 0)\n        self.assertEqual(summary["recent_relevant_awards"], 1)\n''',
)

# Hosted UI regression focused on source semantics.
e2e = ROOT / "tests/e2e/city-record-semantics.spec.ts"
e2e.write_text('''import { expect, test } from '@playwright/test'\nimport { signInForProject } from './auth.helpers'\nimport { expectContained, isIphoneProject } from './iphone.helpers'\n\ntest.setTimeout(180_000)\n\ntest('City Record sentinel deadlines are not presented as genuine open deadlines', async ({ page }, testInfo) => {\n  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)\n  await signInForProject(page, testInfo.project.name, '#/opportunities')\n  const workspace = page.locator('section.opportunities-page')\n  await expect(workspace).toBeVisible()\n  await expect(workspace).toContainText('Unverified deadlines')\n  const search = workspace.getByLabel('Search procurement')\n  await search.fill('20240411118')\n  const row = workspace.locator('.procurement-table tbody tr').first()\n  await expect(row).toContainText('Deadline unverified')\n  await expect(row).toContainText('9999-09-09')\n  await expect(row).not.toContainText('due date')\n  await expectContained(page)\n})\n''', encoding="utf-8")
