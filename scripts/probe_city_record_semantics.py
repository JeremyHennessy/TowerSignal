from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

RESOURCE_URL = "https://data.cityofnewyork.us/resource/dg92-zbpx.json"
REQUEST_IDS = ("20240411118", "20201013110", "20170329022")
FIELDS = (
    "request_id", "pin", "type_of_notice_description", "section_name", "short_title",
    "start_date", "end_date", "due_date", "document_links", "printout_1", "other_info_1",
)

where = "request_id in (" + ",".join(repr(value) for value in REQUEST_IDS) + ")"
params = {"$select": ",".join(FIELDS), "$where": where, "$order": "request_id ASC"}
url = f"{RESOURCE_URL}?{urlencode(params)}"
request = Request(url, headers={"User-Agent": "TowerSignalSourceProbe/1.0", "Accept": "application/json"})
with urlopen(request, timeout=60) as response:
    payload = json.load(response)

if not isinstance(payload, list):
    raise SystemExit("Unexpected City Record response")
by_id = {str(row.get("request_id")): row for row in payload if isinstance(row, dict)}
missing = [request_id for request_id in REQUEST_IDS if request_id not in by_id]
if missing:
    raise SystemExit(f"Missing expected request IDs: {missing}")

for request_id in REQUEST_IDS:
    print(json.dumps(by_id[request_id], sort_keys=True))

print(json.dumps({
    "source_url": url,
    "row_count": len(payload),
    "request_ids": list(REQUEST_IDS),
    "observations": {
        request_id: {
            "due_date": by_id[request_id].get("due_date"),
            "document_links": by_id[request_id].get("document_links"),
            "type": by_id[request_id].get("type_of_notice_description"),
            "section": by_id[request_id].get("section_name"),
        }
        for request_id in REQUEST_IDS
    },
}, indent=2, sort_keys=True))
