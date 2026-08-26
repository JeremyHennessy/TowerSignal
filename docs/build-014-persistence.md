# Build 014 — Persistent prospect workflow

Status: implementation in progress on `agent/build014-persistent-prospect`.

## Scope

Build 014 adds user-owned workflow state without changing TowerSignal's public-source evidence or Priority Score 1.0 semantics.

Planned/implemented workflow state:

- browser-local saved views remain available while signed out;
- signed-in saved views sync to a private durable store;
- named watchlists;
- account disposition/status;
- private notes;
- next-action date;
- watched-account filtering across Prospect, Map and Monitor;
- CRM-oriented workflow export with user fields explicitly prefixed `workflow_*`.

## Persistence architecture

The minimum durable layer is an isolated Neon Postgres project using Managed Better Auth + Neon Data API + PostgreSQL row-level security. The GitHub Pages application never receives a Postgres password. Browser requests use the signed-in user's JWT, and RLS restricts workflow tables to rows owned by `auth.user_id()`.

User workflow state is separate from TowerSignal's source-backed evidence model and must never become scoring or compliance evidence.

## Database development branch

Schema development is isolated on Neon branch `build014-persistent-prospect` (`br-calm-bread-augxbnv8`). Production database schema promotion is intentionally deferred until the code branch is CI-green and the migration is separately reviewed.

## Acceptance remaining

Before merge/production closeout:

1. standard repository CI green on exact head;
2. focused workflow regression tests added and green;
3. database schema promoted through a reviewed migration;
4. production auth trusted-domain configuration includes the GitHub Pages origin;
5. cross-session/device proof for the same signed-in user;
6. hosted Chromium + iPhone/WebKit verification;
7. verify public evidence/scoring/history/source-health behavior remains unchanged.
