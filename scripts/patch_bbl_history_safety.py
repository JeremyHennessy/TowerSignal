from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_history() -> None:
    path = ROOT / "scripts/towersignal/history.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '    return {\n        "system_id": system["system_id"], "bin": system.get("bin"), "bbl": system.get("bbl"),\n        "address": system.get("address"), "borough": system.get("borough"), "zip": system.get("zip"),\n',
        '    return {\n        "system_id": system["system_id"], "bin": system.get("bin"), "bbl": system.get("bbl"),\n        "registry_bbl": system.get("registry_bbl"), "bbl_identity_status": system.get("bbl_identity_status"),\n        "bbl_identity_basis": system.get("bbl_identity_basis"),\n        "address": system.get("address"), "borough": system.get("borough"), "zip": system.get("zip"),\n',
        "durable BBL provenance",
    )

    text = replace_once(
        text,
        'def detect_changes(previous: dict[str, Any], current: dict[str, Any], detected_at: str) -> list[dict[str, Any]]:\n    events: list[dict[str, Any]] = []\n',
        'def detect_changes(previous: dict[str, Any], current: dict[str, Any], detected_at: str) -> list[dict[str, Any]]:\n    events: list[dict[str, Any]] = []\n'
        '    # A newly recovered canonical BBL can expose years of historical property evidence in one build.\n'
        '    # That is an identity/enrichment backfill, not a real-world event observed on detected_at. Suppress\n'
        '    # BBL-derived PLUTO/HPD/DOB events for this one transition only. Core SYSTEM_ID evidence remains live.\n'
        '    identity_backfill = (\n'
        '        current.get("bbl_identity_status") == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL"\n'
        '        and not previous.get("bbl")\n'
        '        and bool(current.get("bbl"))\n'
        '    )\n',
        "identity-backfill guard",
    )

    text = replace_once(
        text,
        '    if current.get("building_context") and previous.get("pluto_owner") != current.get("pluto_owner"):\n',
        '    if not identity_backfill and current.get("building_context") and previous.get("pluto_owner") != current.get("pluto_owner"):\n',
        "PLUTO backfill guard",
    )
    text = replace_once(
        text,
        '    if current_hpd_present and any(previous.get(field) != current.get(field) for field in registration_fields):\n',
        '    if not identity_backfill and current_hpd_present and any(previous.get(field) != current.get(field) for field in registration_fields):\n',
        "HPD registration backfill guard",
    )
    text = replace_once(
        text,
        '    if current_hpd_present:\n        for key, contact in current_contacts.items():\n',
        '    if current_hpd_present and not identity_backfill:\n        for key, contact in current_contacts.items():\n',
        "HPD contacts backfill guard",
    )
    text = replace_once(
        text,
        '    events.extend(_detect_dob_changes(previous, current, detected_at))\n    return events\n',
        '    if not identity_backfill:\n        events.extend(_detect_dob_changes(previous, current, detected_at))\n    return events\n',
        "DOB backfill guard",
    )
    path.write_text(text, encoding="utf-8")


def patch_test_history() -> None:
    path = ROOT / "tests/python/test_history.py"
    text = path.read_text(encoding="utf-8")
    anchor = '    def test_removed_system_wording_is_snapshot_presence_not_decommissioning(self):\n'
    test = '''    def test_recovered_bbl_backfill_does_not_emit_synthetic_property_events(self):
        previous = full_observation(
            system={"bbl": None},
            building_context=None,
            hpd_registration=None,
            dob_activity=[],
        )
        current = full_observation(
            system={
                "bbl": "3000017501",
                "registry_bbl": None,
                "bbl_identity_status": "RECOVERED_EXACT_BIN_MAPPLUTO_BBL",
                "bbl_identity_basis": "EXACT_BIN_UNIQUE_MAPPLUTO_BBL",
                "active_equipment": 3,
            },
            building_context={"owner_name": "HISTORICAL OWNER LLC"},
            hpd_registration={
                "registration_id": "R-BACKFILL",
                "last_registration_date": "2024-08-01",
                "contacts": [{
                    "registration_contact_id": "C-BACKFILL",
                    "type": "Managing Agent",
                    "description": "Managing Agent",
                    "corporation_name": "HISTORICAL MANAGEMENT LLC",
                }],
            },
            dob_activity=[dob_job(
                filing_date="2023-06-01",
                first_permit_date="2023-07-01",
                approved_date="2023-06-15",
                job_description="Historical cooling tower work",
                explicit_cooling_tower_mention=True,
            )],
        )
        events = detect_changes(previous, current, "2026-09-07T17:00:00Z")
        event_types = {event["event_type"] for event in events}
        self.assertIn("ACTIVE_EQUIPMENT_CHANGED", event_types)
        self.assertNotIn("PLUTO_OWNER_CHANGED", event_types)
        self.assertFalse(any(event_type.startswith("HPD_") for event_type in event_types))
        self.assertFalse(any(event_type.startswith("DOB_") for event_type in event_types))

        snapshot, changes = build_history(
            [current],
            "2026-09-07T17:00:00Z",
            history_snapshot(previous),
            [],
        )
        self.assertEqual(snapshot["systems"][0]["bbl"], "3000017501")
        self.assertEqual(snapshot["systems"][0]["bbl_identity_status"], "RECOVERED_EXACT_BIN_MAPPLUTO_BBL")
        self.assertFalse(any(event["event_type"].startswith(("PLUTO_", "HPD_", "DOB_")) for event in changes["events"]))

'''
    if anchor not in text:
        raise RuntimeError("test_history insertion anchor missing")
    text = text.replace(anchor, test + anchor, 1)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_history()
    patch_test_history()
