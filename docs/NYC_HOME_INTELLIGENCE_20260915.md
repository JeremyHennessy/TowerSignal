# NYC Home official intelligence

## User scope

Move the `Legionnaires official intelligence` block from Prospect to Home. Improve the table and link official findings to systems in the NYC application. GitHub Pages only. Do not modify Azure, Toronto, Priority Score, Sales Pack or Technician Pack in this release.

## Preserved baseline

- Application main: `7eeb4a47e4be92ee8d9e16640705c97e8b93496b`.
- Pages source run: `34997430388`, artifact `10411008631`, digest `sha256:d451b1bbb6ca14c240511d6e31d7ff2ff2a325f99ddc3f0e2bc69936ff12f636`.
- Full actual-hosted desktop/iPhone acceptance and history persistence: `35009880669`, test source `3ba37f707b4803096cfaeddb9ac801456f0658ec`. The failed original test expected History metrics while Evidence mode was selected. This release preserves the already-proven mode-correct assertion.
- Full desktop/iPhone screenshot inventory: `35010254349`. The Home hero, navigation, summary cards, workspace cards and unrelated account UI stay unchanged.

## New presentation

A Home-only scoped component below the existing summary cards provides date/source columns, evidence badges, search, six-row pagination, linked-building expansion and responsive mobile rows. The twelve-channel count comes from the published payload. Source or matching failure is explicitly unavailable, not zero.

## Matching contract

An official results-list address must match a normalized registry address in the same borough and resolve to exactly one nonempty BIN. All systems at that named building are linked as building context, never individually labeled positive. Ambiguous and unmatched addresses remain unresolved. Town-hall venues and broad Bronx title matches are excluded. Related earlier articles link to a separate later document explicitly, not as a claim that the earlier article names the building. PCR, culture, cleaning and closed-cluster status remain separate.

The South Bronx September 2026 named list and the linked Upper East Side official PDF results are source-specific adapters. Their source hashes, document dates, retrieval times and original address evidence are retained. They do not establish exhaustive matching of every historical news item. Source proof run `35015592838` established that `pdftotext` is absent on the hosted runner. The proof and ordinary Pages workflow explicitly install `poppler-utils` before extraction.

`legionella-property-matches.json` is additive. Every existing published source payload and every existing score is preserved byte-for-byte in this application release. The original alert collector remains unchanged. The ordinary NYC Pages workflow builds the match index after all registry attachments and history generation, so its recorded registry checksum identifies the final published systems payload. No earlier source builder is repurposed as a matching hook.

## Release control

The branch proof must pass source extraction, all repository checks, exact-source preservation and the full candidate desktop/iPhone suite. Inspect the attached candidate screenshots before merging. Merge only the exact tested head with `[skip ci]` to avoid starting a second ordinary publisher. Dispatch `home-intelligence-release.yml` with the exact PR/head/proof. That workflow checks tree identity, promotes the pretested artifact, verifies hosted bytes and runs the full browser suite. Failed acceptance restores and verifies the original artifact.

## Separate work still pending

The user requested a revised `Why this score` model. The `priority_v2` work is a separate, uncalibrated candidate. This Home/matching release does not silently adopt those weights or claim improved predictive accuracy.
