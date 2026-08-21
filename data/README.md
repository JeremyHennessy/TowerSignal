# Data handling

TowerSignal does not commit the full NYC source datasets. The Pages workflow retrieves the authoritative NYC Open Data cooling-tower registration and inspection datasets at build time, validates them, and creates optimized static JSON inside the deployment artifact.

Build 002 also queries the NYC OATH Hearings Division Case Status dataset (`jz4z-kudi`) only for ticket numbers that correspond to published cooling-tower inspection summons numbers. The full OATH dataset is not downloaded or shipped to the browser. OATH provenance records the scoped-query row count, requested ticket count, exact matched ticket count, source update timestamp, and match basis.

`data/fixtures/` contains small deterministic synthetic records for tests only. Fixture records are never used by the production Pages build.
