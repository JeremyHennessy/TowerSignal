import json
import tempfile
import unittest
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from scripts import build_data_live as pipeline
from scripts.towersignal.hpd_identity import assemble_contacts, index_registrations
from scripts.towersignal.acris_identity_cache import property_targets
from scripts.towersignal.acris import _condo_target_index
from scripts.validate_bbl_identity import validate as validate_identity


class MappingBuildTests(unittest.TestCase):
    def test_complete_core_build_preserves_contacts_sampling_and_source_address_parts(self):
        # Production-volume synthetic fixtures exercise the complete builder and
        # its real validators. Only external collection is replaced.
        base = {"bin": "1089723.0", "bbl": "1011710154", "date_registered": "2020-01-01", "number": "400", "street": "WEST 61ST STREET", "borough": "MANHATTAN", "zip": "10023", "sampledates": "", "activeequipment": "1"}
        registrations = [{**base, "system_id": str(2000100000 + i)} for i in range(3500)]
        registrations[0]["system_id"] = "2000014227"
        inspection = {key: "" for key in pipeline.validate_sources.__globals__["EXPECTED_INSPECTION_FIELDS"]}
        inspection.update(system_id="2000014227", inspection_date="2020-01-01", inspection_type="ROUTINE", active_equip="1")
        inspections = [inspection] * 50000
        def snapshot(dataset, rows):
            return SimpleNamespace(dataset_id=dataset, name="Synthetic source fixture", rows=rows, retrieved_at="2020-01-01T00:00:00Z", source_record_count=len(rows), source_last_updated_at="2020-01-01T00:00:00Z")
        def meta(**values):
            return defaultdict(int, {"dataset_id": "fixture", "name": "Synthetic fixture", "retrieved_at": "2020-01-01T00:00:00Z", "url": "https://example.invalid/fixture", "source_query_scope": "synthetic exact-key fixture", "source_last_updated_at": "2020-01-01T00:00:00Z", **values})
        registration = {"registrationid": "123", "buildingid": "456", "bin": "1089723", "boroid": "1", "block": "1171", "lot": "154", "lastregistrationdate": "2020-01-01"}
        index = index_registrations([registration])
        hpd_meta = meta(registration_dataset_id="tesw-yqqr", contacts_dataset_id="feu5-w2e2", matched_registration_bbl_count=1, matched_contact_bbl_count=1)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(pipeline, "fetch_dataset", side_effect=[snapshot("y4fw-iqfr", registrations), snapshot("f9wb-g8mb", inspections)]))
            stack.enter_context(patch.object(pipeline, "fetch_oath_cases", return_value=({}, meta())))
            stack.enter_context(patch.object(pipeline, "fetch_planimetric_towers_by_bin", return_value=({}, meta())))
            stack.enter_context(patch.object(pipeline, "fetch_building_footprints_by_bin", return_value=({"1089723": [{"bin": "1089723", "base_bbl": "1011710154", "mappluto_bbl": "1011717513"}]}, meta())))
            stack.enter_context(patch.object(pipeline, "fetch_registration_snapshot", return_value=index))
            stack.enter_context(patch.object(pipeline, "fetch_pluto_by_bbl", return_value=({"1011717513": {"bbl": "1011717513", "owner_name": "Synthetic Owner"}}, meta())))
            stack.enter_context(patch.object(pipeline, "fetch_dob_activity_by_bbl", return_value=({}, meta())))
            stack.enter_context(patch.object(pipeline, "fetch_contacts_for_systems", side_effect=lambda systems, idx: (assemble_contacts(systems, idx, [{"registrationid": "123", "firstname": "Synthetic", "lastname": "Agent"}]), hpd_meta)))
            output = Path(tmp)
            payload = pipeline.build(output)
            validate_identity(output, require_production_volume=True)
            row = next(s for s in payload["systems"] if s["system_id"] == "2000014227")
            detail = json.loads((output / "details/20/2000014227.json").read_text())
            self.assertEqual(row["hpd_contact_count"], len(detail["hpd_registration"]["contacts"]))
            self.assertEqual(row["hpd_contact_count"], 1)
            self.assertEqual(detail["sample_history"]["dates"], [])
            self.assertEqual(row["number"], "400")
            self.assertEqual(detail["identity"]["street"], "WEST 61ST STREET")
            self.assertEqual(row["source_bin_raw"], "1089723.0")
            self.assertEqual(row["bin"], "1089723")
            self.assertEqual(row["bbl"], "1011717513")
            self.assertTrue(_condo_target_index(property_targets([row])))


if __name__ == "__main__":
    unittest.main()
