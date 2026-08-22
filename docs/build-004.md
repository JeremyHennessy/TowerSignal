# Build 004 — HPD registered ownership and managing-agent context

Build 004 adds public NYC Department of Housing Preservation and Development registration contacts for cooling-tower properties that are covered by HPD Multiple Dwelling Registration.

## Join semantics

TowerSignal uses only exact identifiers:

`cooling-tower BBL` → `HPD Multiple Dwelling Registration borough/block/lot` → `HPD registration_id` → `Registration Contacts registration_id`

No address similarity, organization-name matching, geospatial proximity, or fuzzy contact inference is used.

## Sources

- HPD Multiple Dwelling Registrations — `tesw-yqqr`
- HPD Registration Contacts — `feu5-w2e2`

HPD registration coverage applies to qualifying residential properties. A cooling-tower property without an HPD match is not treated as lacking an owner, manager, or service contact.

## Product semantics

Published HPD contact roles, names, organizations and business mailing addresses are commercial research context. They do not alter TowerSignal Priority Score model 1.0, do not establish cooling-tower compliance, and do not prove that a listed person or organization purchases or controls cooling-tower services.
