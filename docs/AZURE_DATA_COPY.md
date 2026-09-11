# Private Blob data copy, 2026-09-11

This migration copies data only. It does not deploy a website, change application
URLs, modify authentication, change container access/CORS/DNS, delete GitHub data,
or write the GitHub history branch. Browser access is not required for this copy.
The existing `azure-production` environment's `AZURE_STORAGE_KEY` authenticates
uploads AND every readback. It is never sent to the frontend or copied to reports.

## Source checkpoint

Repository baseline: `21fd66dabf0bc41eb282baa7b38dd835efb9422c`.
Pages release: `34544249376`, application commit
`53f7016404774821051e5ebd02eeb5382dded55f`, successful attempt 2.
`config/azure-data-copy-20260911.json` pins artifact IDs, archive SHA-256 checksums,
required runtime files and data-branch commit SHAs. This is a frozen migration,
not a new source collection run and not a freshness refresh.

## Copied scope

* Every regular file under the verified Pages artifact's `data/`, including all
  account/firm detail shards, city/state datasets, water, procurement, coverage,
  source-health, history and scoring/validation payloads. No fixture substitution.
* Original Pages and history-state ZIP artifacts for exact recovery/provenance.
* All persisted data/history, data/acris and data/checkbook files at pinned commits.
* Checked-in data, config and SQL schema files in a separate support/repository
  area. Test fixtures stay here; they are never mixed into production runtime data.
* An explicit absent-source record for `data/oath` if the inspected branch still
  contains no cache there. OATH observations already in runtime data are copied.

Live Neon user/workflow records and browser-local saved state are not stored in
GitHub and are outside this copy. Expired or unpublished intermediate artifacts,
other repositories (including Toronto), and historical Git commit versions are
not represented as migrated production data.

## Execution and verification

Workflow: **Copy verified TowerSignal data to private Blob**, manual dispatch on
main only. No push or schedule trigger. The job first confirms the source release
and its four required jobs passed, downloads the pinned artifacts, verifies their
archive SHA-256, safely extracts every runtime file, and checks snapshot files
against their canonical Git blob hashes. It computes a SHA-256 manifest for all
staged files before obtaining the Azure key in the upload step.

Destination is strictly `pharm3r/data/towersignal-data`. A unique directory per
migration run and attempt prevents overwriting previous copies:

```
towersignal-data/migrations/github-<run-id>-<attempt>/
  runtime/                 # Contents of production data/, paths preserved
  support/history/         # Pinned durable history
  support/acris/            # Pinned ACRIS cache
  support/checkbook/        # Pinned Checkbook cache
  support/repository/       # Fixtures, config, schema, separate from runtime
  archives/                # Original digest-verified artifact ZIPs
  provenance.json
  _migration/manifest.json
  _migration/complete.json
```

Uploads are create-only. Every file is then downloaded using authenticated Blob
access and checked byte-for-byte via SHA-256 AND size. Metadata checks alone do
not count as verification. A full listing restricted to this migration prefix
must exactly match the manifest. Only then are the manifest and COMPLETE receipt
published and themselves read back. The job retains a checksummed inventory and
transfer receipt as a GitHub artifact for 30 days.

Partial copies have no verified COMPLETE receipt and are not used by any app.
A failed run does not switch a live pointer or delete anything. Rerunning produces
a different attempt directory. Keep GitHub as the existing source until a
separately approved pipeline/read-path change. This copy does not automatically
redirect future source workflows to Blob.

## Merge control

Merge only the tested PR head. This migration tooling does not alter application
files. A `[skip ci]` merge message prevents the otherwise unrelated push-triggered
Pages refresh; repository CI must already have passed on that exact branch head.
Dispatch the data-copy workflow separately after merge. Never put the account key
in code, normal variables, logs or artifacts.
