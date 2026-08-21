# Data handling

TowerSignal does not commit the full NYC source datasets. The Pages workflow retrieves the authoritative NYC Open Data datasets at build time, validates them, and creates optimized static JSON inside the deployment artifact.

`data/fixtures/` contains small deterministic synthetic records for tests only. Fixture records are never used by the production Pages build.
