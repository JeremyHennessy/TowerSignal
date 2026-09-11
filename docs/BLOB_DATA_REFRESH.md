# Website-independent data refresh

## Custody and scope

Starting code: `bc29f20b4be89989ce7b29c781944e722fc4fd2a` (PR #224).
The existing verified runtime/history selector references Pages release
34544249376 through the immutable-by-convention migration snapshot
`towersignal-data/migrations/github-34593386563-1/`.

`azure-data-refresh.yml` is a new producer, not a site release. It runs manually
or at **10:17 UTC daily**, the existing production data cadence. Its two jobs are
`generate` and `publish`; their GitHub permissions are read-only. There is no
Pages configuration, deployment, Static Web Apps, DNS, auth, source-policy,
frontend URL, or GitHub history-branch write. Existing files/workflows are not
modified by this addition.

## Generation contract

All original run steps from "Fetch, validate and generate current NYC data"
through "Production build" in `pages.yml` appear verbatim, in the same order,
with the same validators, samples, optional ACRIS gate and per-step limits.
An offline regression enforces this exact block. The new generation job has a
240-minute overall bound; source-specific bounds are not increased. A failure
stops that candidate; no reduced-volume, stale-source, or fixture fallback is used.

Before collection, the job reads the current Blob pointer and verified history
manifest, restores every previous history file with SHA-256/size verification,
and retains the exact parent pointer bytes and ETag. No fallback to stale Git
observation history is permitted. This is essential for the second and later
Blob-only refreshes to compare with their actual previous observation.

ACRIS and Checkbook continue to come from the existing verified Git data branches.
The independently refreshed OATH cache comes from `data/towersignal-history`,
not a nonexistent `data/oath` cache. Only the OATH **source-cache file** is overlaid
onto the local restored inputs; previous latest/events/segments stay identical
to Blob. Each input records its Git commit, Git blob SHA and SHA-256. Existing
freshness limits are also checked before expensive source collection. Source-cache
writer migration is a separate task; expiry fails rather than silently borrowing
old data or changing dates.

After the full build, Chromium and WebKit test the actual generated files over a
local HTTP server. They check NYC/NYS lists, account and firm detail paths,
history/source-health structures and a genuine missing-file 404. This is **data
transport acceptance**, not hosted UI, login or Azure frontend verification.
No mock data, authentication bypass, public hosting or external test user is used.

Sealing requires `dist/data` and `public/data` to have identical file inventories
and checksums, fresh generation timestamps within the current run, and unchanged
source inputs. All runtime files are retained. New durable history is the same
projection written by the original Pages history job, plus retained source inputs
such as the verified OATH cache. Runtime/history byte parity is checked before
creating the data-only artifact.

## Publication and authority

The separate publish job starts only after successful generation and acceptance.
It checks the actual trusted main workflow/run identity and successful generate
job. It retrieves the unique artifact belonging to that job's time window and
verifies GitHub's artifact digest, source SHA, exact archive layout, file paths,
file inventories and per-file hashes. Artifacts contain data, not executable code
or credentials. Read credentials are not passed to artifact redirect hosts.

Candidate output locations:

```
towersignal-data/releases/data-<run-id>-<generation-attempt>/runtime/**
towersignal-data/releases/data-<run-id>-<generation-attempt>/_publication/**
towersignal-data/state/history/data-<run-id>-<generation-attempt>/files/**
towersignal-data/state/history/data-<run-id>-<generation-attempt>/_publication/**
```

The existing publisher's verified transfer/inventory/receipt primitives are reused.
The new adapter allows create-only writes only under these data-release paths;
no migration snapshot, existing cache, unrelated company file, or selector can
be rewritten through its create method. Full Blob SHA-256 readback, directory-aware
inventory, and stable ETags must pass before completion receipts are created.

The sole mutable pointer remains `pointers/production-current.json`, selecting
both runtime and matching history. Publication is a lineage-based conditional
update against the **same parent ETag loaded before collection**. If the parent
changed, the candidate cannot replace it. Exact previous pointer bytes are backed
up in the new publication directory. Selectors are verified but not modified.
A failed publish retains the old pointer; incomplete candidates can remain for
inspection and are never selected. No automatic deletion is performed.

A successful data-only source is explicitly labelled `kind: data-only`, with its
actual workflow ID/path and attempt. It is NOT labelled a successful Pages
release, and run numbers from different workflows are NOT compared. The existing
Pages-only publisher deliberately does not recognize this authority: after the
first data-only promotion it fails closed rather than replacing Blob history
with a Pages release based on stale Git observation history. Re-enabling the old
Pages publisher as a writer requires an explicit reader/lineage migration first.

An identical retry verifies the current data without advancing it. Publishing-only
retries may use the previously successful generate job's sealed artifact after
rechecking its provenance. A new generation attempt receives a separate version
path and must start from the then-current Blob history.

## First live acceptance

Merge only the exact CI-passing head without initiating an unrelated Pages refresh.
Run `Refresh TowerSignal data to private Blob` manually on main. Check:

1. Paired Blob history and source cache preflight succeed.
2. Every original generation/validation step, frontend check/build and data browser
   test succeeds; a sealed candidate artifact is present.
3. The publish job reports `DATA_REFRESH_RESULT` with `CURRENT`, updated generation
   dates, actual file/byte counts, and a new matched runtime/history descriptor.
4. The result artifact and read-back pointer match. The original snapshot and
   GitHub history branch must not be attributed changes made by this producer.

A queued run, successful merge or source-copy receipt is not proof of a fresh
refresh. While the long-running collectors execute, the old verified pointer
remains current. A full newly generated live success is required before claiming
freshness or a successful first independent data cycle.

## Operational recovery

On a validation error inspect that source's step/log and repair only the failing
layer. Do not lower the existing limits, regenerate keys, enable public access or
roll back the verified dataset to hide a failed candidate. On a parent ETag
conflict, regenerate from the new current history; do not overwrite the guard.
Disabling this one workflow stops future data-only refreshes without deleting
any retained version. A deliberate rollback requires verifying the saved previous
pointer's datasets and applying a conditional pointer update; no automatic
rollback or garbage collection is introduced here.

GitHub documents scheduled workflows and job dependencies in
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax .
Azure's conditional ETag update semantics are documented in
https://learn.microsoft.com/en-us/azure/storage/blobs/concurrency-manage .
