# ADR-0003: Promote Immutable Catalog Snapshots Atomically

## Status

Accepted

## Date

2026-08-01

## Context

An import can fail after a package is received but before all records are usable. Readers
must never observe a partial catalog, and operators need enough history to diagnose a run
or return to a known-good catalog without rebuilding data.

Song freshness also has different semantics from import freshness. An unchanged song
should retain the time its semantic content last changed, while the catalog timestamp is
the completion time of the active import.

## Decision

The importer privately stores the received package, validates the V1 manifest and every
record, then creates a complete candidate snapshot inside a PostgreSQL transaction. It
derives rights defaults, semantic fingerprint columns, freshness timestamps, and search
documents on the server. Only after staging succeeds does the same transaction mark the
snapshot complete and replace the singleton active-snapshot pointer.

Completed entries and snapshots are immutable through application interfaces. Promotion
and rollback change only the active pointer and append an activation record. Activation
records retain snapshot UUIDs even after retention deletes their materialized rows. The
active snapshot plus seven prior successful snapshots are retained; package, report, run,
and event history remain available independently.

The exporter-generated `run_id` is the idempotency identity. Repeating the same package
returns the existing run; different package bytes under that identity are rejected. A
song retains `content_changed_at` only when both `song_uid` and the semantic fingerprint
match the prior active snapshot. New or changed songs receive the successful promotion
time. Imported rights always start as `unknown`.

Packages and reports use a dedicated private storage alias and production bucket. They
are never exposed through public media storage or a public URL.

The machine-facing JSON import endpoint is registered through Django Bolt and served by
the dedicated Bolt service. Django/Reactivated views remain the transport for rendered
UI; the importer service itself is independent of either transport.

## Alternatives Considered

### Update one mutable catalog in place

Rejected because readers could observe mixed versions and rollback would require a
second reconstruction operation.

### Promote before building search documents

Rejected because an active snapshot would temporarily be incomplete and search readiness
would become a separate failure mode.

### Use ZIP bytes as the only identity

Rejected because ZIP metadata may change across transport retries. `run_id` expresses the
business attempt while both transport and record fingerprints detect conflicts.

## Consequences

- A failed validation or staging transaction leaves the active catalog unchanged.
- Rollback is fast and does not mutate catalog content.
- Retention bounds materialized catalog storage without deleting import diagnostics.
- Import transactions are intentionally heavier because all derived fields must be ready
  before promotion.
- Search ranking, query indexes, and the public read API remain slice 4 concerns.
