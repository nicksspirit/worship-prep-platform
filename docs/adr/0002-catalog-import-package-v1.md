# ADR-0002: Define a Storage-Neutral Catalog Import Package

## Status

Accepted

## Date

2026-08-01

## Context

The Catalog Exporter runs beside EasyWorship on Windows while the Catalog Importer
runs in Worship Prep Platform. The boundary must preserve enough source evidence to
diagnose and reprocess imports without coupling the exporter to PostgreSQL or exposing
private EasyWorship data through application tables.

The observed source consists of `Songs.db` metadata joined from `song.rowid` to
`SongWords.db.word.song_id`. `SongKeys.db` is a derived, incomplete search index.
EasyWorship RTF contains free-form hidden section labels and slide markers, and the
source contains known usable slide-cardinality anomalies. Opaque revision values and
SQLite file checksums are evidence, not authoritative content-change signals.

## Decision

Use a versioned ZIP contract named `catalog-import/v1` containing `manifest.json` and
`songs.ndjson`. The manifest carries Catalog Import Run identity, exporter/parser
versions, copied-source checksums, counts, warnings, and an exact records checksum.

Each song record preserves opaque identity, metadata, raw RTF, revisions, ordered
slide UIDs, and presentation evidence. It also carries cleaned lyrics, ordered Song
Sections/slides, and a versioned componentized semantic fingerprint. `song_uid` is the
sole stable catalog identity. Recognized numbered labels normalize without numbering;
unrecognized labels remain exact. Structural anomalies are reported as warnings when
the song remains usable.

The package contains no PostgreSQL search vectors, database primary keys, rights
decisions, or catalog timestamps. Those remain responsibilities of the Catalog
Importer and Song Catalog.

The exporter registers a placeholder for EasyWorship's unavailable `UTF8_U_CI`
collation only to parse the SQLite schema. It forces source-table scans and never uses
or claims to validate EasyWorship index ordering.

## Alternatives Considered

### Upload the SQLite databases directly

Rejected because it would couple importer correctness to undocumented schemas,
collations, and future source changes while postponing deterministic normalization.

### Emit PostgreSQL-ready rows and search documents

Rejected because it would give a Windows client ownership of server storage and search
semantics and make contract reuse harder.

### Treat every structural anomaly as fatal

Rejected because the profiled 2,283-song EasyWorship Library contains 193 known
slide-UID/marker anomalies while remaining operationally usable.

## Consequences

- Slice 3 can validate one explicit, shared package boundary before staging data.
- Raw source evidence remains private and recoverable for parser improvements.
- Fingerprint versions can evolve independently of opaque EasyWorship revisions.
- A breaking contract change requires a new version and shared fixture set.
- The importer must verify archive shape, schemas, counts, and checksums rather than
  trusting exporter output.
