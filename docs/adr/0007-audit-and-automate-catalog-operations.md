# ADR-0007: Audit and Automate Catalog Operations

## Status

Accepted

## Date

2026-08-01

## Context

The active Catalog Entry belongs to an immutable imported snapshot, while Lyrics Rights
Status is an administrative policy that may change independently of EasyWorship
content. A rights decision must immediately govern every retained read surface, survive
the next import, and preserve evidence without rewriting private source packages.

Catalog operations also cross the Windows and hosted-platform boundary. The web app
must never reach into EasyWorship, so the weekly trigger and connectivity retry must run
beside the EasyWorship Library. Django must still retain one coherent Catalog Import Run,
make failed packages recoverable, alert Superusers, and expose rollback and diagnostics.

## Decision

Store current Lyrics Rights Provenance in a record keyed by stable `song_uid`, with an
append-only change history containing the old and new status, policy basis, evidence
reference, explanation, deciding Superuser, and timestamp. Imported identities without
a record create an `unknown` record. A decision transaction updates the current record,
appends its audit row, and updates the deliberately denormalized `rights_status` policy
overlay on every retained Catalog Entry for that identity. Future snapshots copy the
current policy during staging. Imported song content and private evidence remain
immutable.

Catalog Administrators may view import history, diagnostics, snapshots, current rights,
and rights history. Only Superusers may change rights, issue/rotate/revoke Integration
Client keys, approve invitations, recover a retained failed package, or activate a
retained snapshot as a rollback. Recovery revalidates the checksum and run identity and
appends events beneath the original Catalog Import Run.

Schedule the Catalog Exporter with Windows Task Scheduler weekly at 3:00 AM on a
configurable weekday (Sunday by default). Installation requires the Windows `Pacific
Standard Time` zone so Windows applies America/Los_Angeles daylight-saving transitions.
The task retries a failed command once after 30 minutes. On retry, the exporter delivers
pending durable work before starting new source acquisition, so the same run and package
are retried rather than creating a second attempt.

Protect the import-scoped API key with current-user Windows DPAPI. Deliver the package
and durable NDJSON exporter timeline together over HTTPS. Django records whether the
attempt was manual or scheduled, synchronizes exporter events idempotently, and emails
active Superusers when a scheduled attempt fails. A successful acknowledgment archives
the local event file; failed connectivity leaves the package and events pending.

Publish the installer as a stable application static asset. It selects the newest
semantic `exporter/v*` release, verifies the binary SHA-256, preserves the exporter
instance identity across updates, configures the task, and runs diagnostics. Tag builds
publish the Windows binary and checksum only after portable, Windows, cross-compile, and
installer gates pass.

## Alternatives Considered

### Mutate only the active Catalog Entry

Rejected because rollback or snapshot-pinned pagination could re-expose an obsolete
rights decision, and the next import would reset the policy.

### Put rights evidence in every immutable snapshot

Rejected because administrative provenance is not EasyWorship source content and would
duplicate sensitive evidence across materialized read models.

### Run the schedule in Django or Cloud Scheduler

Rejected because the hosted application cannot and must not access the on-premises
EasyWorship Library. Scheduling source acquisition at the Windows boundary keeps that
authority explicit.

### Let a retry generate a new run ID

Rejected because one operational attempt must keep the same identity across local work,
delivery, platform processing, alerts, and retries.

## Consequences

- Rights changes take effect across public and Integration Client reads without leaking
  provenance outside Catalog Administration.
- The rights policy overlay is mutable, but imported snapshot content remains immutable.
- Scheduled delivery depends on the designated Windows account and Pacific time-zone
  configuration; diagnostics fail clearly when either assumption is not satisfied.
- Catalog Import delivery now accepts an optional exporter-event attachment and trigger
  header in addition to the V1 package.
- Production release still requires the real EasyWorship Windows smoke environment; CI
  verifies the portable and Windows adapter contracts but cannot manufacture that
  external source environment.
