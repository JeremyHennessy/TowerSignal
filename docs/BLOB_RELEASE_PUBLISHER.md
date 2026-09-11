# Runtime and history Blob publication

## Scope and checkpoint

The approved migration snapshot remains create-only by convention at
`towersignal-data/migrations/github-34593386563-1/`. This is not an Azure
immutability-policy change. Do not edit, move, or delete this snapshot.
The new publisher cannot write under `migrations/` at all.

Starting application/repository baseline: `a2552d9ea7697a0854f4752aa10850dcad4bff4e`.
Verified source Pages release: `34544249376`, application SHA
`53f7016404774821051e5ebd02eeb5382dded55f`. Bootstrap history is pinned to
`ec888b6bbba931d98efa50cdbef81125d18ec70b`.

The repository was private and GitHub reported `has_pages: false` when this work
started on 2026-09-11. This change does not re-enable or deploy Pages, create a
Static Web App, change frontend URLs, refresh source observation dates, or alter
authentication. A publisher cannot manufacture a new successful data release
while its producer is inactive.

## Workflow and release gates

`azure-data-publish.yml` is a separate, non-cancelling `workflow_run` follower of
`Deploy GitHub Pages`, plus a manual entry point. Existing Pages build/source
steps and the GitHub history writer are untouched. Keeping Azure publication
outside the producer prevents an Azure outage from cancelling a verified Pages
release or stopping its existing history persistence.

The follower validates the actual upstream repository, workflow ID/path,
main branch, event type and successful build/deploy/verify/persist-history jobs.
PR or fork runs are rejected. It checks out only the trusted publisher commit,
never upstream artifact code. Artifacts are data only; unsafe paths, links,
duplicate members and inconsistent inventories are rejected. ZIP checksums,
artifact source SHA and the successful build's timestamps bind each input.

Normal publication preserves every runtime file. The source history-state
artifact, runtime history and the generated portion of the GitHub history tree
must match byte-for-byte. The full GitHub `data/history/` snapshot is retained,
including separately persisted inputs such as `oath-cache.json.gz`. Other
persisted inputs are reported explicitly; they are not represented as new
runtime observations. History Git blob SHA values are checked on Blob readback.
A changed GitHub history head blocks promotion rather than combining releases.

## Storage contract

All data stays private in `pharm3r`, container `data`, under `towersignal-data/`.
Only the existing `azure-production` environment credential is used.

```
releases/pages-<source-run-id>/runtime/**
releases/pages-<source-run-id>/_publication/runtime/{manifest,complete}.json
state/history/pages-<source-run-id>/files/**
state/history/pages-<source-run-id>/_publication/{manifest,complete}.json
pointers/production-current.json
pointers/runtime-current.json
pointers/history-current.json
```

Bootstrap points the dataset descriptors at the existing migration's runtime
and history directories. It writes only new publication manifests/receipts and
pointers; it does not upload another dataset copy.

Normal publication uses create-only writes, full authenticated SHA-256/size
readback, exact paginated inventory reconciliation, independently confirmed
manifest-parent directory markers, and unchanged payload ETags. A complete
receipt is written only after these checks. Existing different bytes at a
release path cause failure, never overwrite.

`production-current.json` is the sole mutable release pointer and contains BOTH
runtime and matching history descriptors. It is created conditionally or updated
with an ETag precondition. The two named runtime/history pointers are immutable
selector documents: resolve `resolve_via` once, then use the named `select` field.
They are not independently updated release pointers. This avoids mixed-version
runtime/history reads; Azure does not make two separate Blob writes atomic.

Older source run numbers cannot replace newer ones. A same-run conflicting
publication fails. An identical current release is reverified without writes.
Before an update, the exact previous current-pointer bytes are stored at
`releases/pages-<new-source-run-id>/_publication/previous-current.json`.
A conditional-write conflict fails rather than blindly overwriting another writer.

## Execution

First run the manual workflow with `operation=bootstrap`. It uses the pinned
source release and verified migration manifest/completion receipt. Then test
`operation=publish`, `source_run_id=34544249376`: it exercises actual artifact
staging, Git history parity and the idempotent already-current path. This does
not rerun data collection or deploy a site.

Subsequent successful ordinary Pages releases trigger publication automatically.
The follower is asynchronous: Pages success and Blob publication success are
separate states. A skipped or failed producer cannot advance Blob current.
The artifacts named `blob-publication-<run-id>-<attempt>` contain source proof,
checksums, parity and the result or failure report. Only a real publication step's
result establishes Azure success; simulated unit-test output does not.

## Rollback and remaining work

Disabling this follower stops future Blob publications without modifying the
source workflows, history branches, existing Blob snapshots, or application.
No current consumer is switched to Blob by this change. A deliberate data-pointer
rollback requires reviewing the saved previous-pointer object, verifying both
referenced datasets, and an ETag-conditional update; the normal publisher will
not automatically downgrade or erase a snapshot. Do not delete failed candidate
payloads or reset the storage key as a response to a verification failure.

ACRIS/Checkbook cache dual-writes, build-reader cutover, standalone source refresh
changes, retention deletion, frontend serving, and Static Web Apps remain
separate tasks. No new anonymous access, CORS rules, SAS tokens, or secrets in
frontend bundles are introduced.

Primary API references used for this contract:
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run
- https://learn.microsoft.com/en-us/azure/storage/blobs/concurrency-manage
- https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-list-python
