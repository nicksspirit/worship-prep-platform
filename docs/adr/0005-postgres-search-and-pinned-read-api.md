# ADR-0005: Use PostgreSQL Search with Snapshot-Pinned Read Resources

## Status

Accepted

## Date

2026-08-01

## Context

Integration Clients need predictable title and lyric discovery over an immutable Song
Catalog while Catalog Imports may activate a new snapshot between page requests. Title
and lyric access have different rights and scope rules, and no continuation may skip or
duplicate songs because the active pointer changed. The V1 catalog is bounded at 10,000
songs, so an external search service would add operational and consistency costs without
measured need.

Clients also need a stable JSON contract, conventional errors, per-key throttling, and
documentation that reflects the types the Django Bolt service actually serializes.

## Decision

Use PostgreSQL as the complete V1 search system. The database owns a project-specific
`wpp_simple_unaccent` text-search configuration copied from `simple`, with `unaccent`
applied before lexeme generation. Store separate title and lyric vectors with GIN
indexes. Title mode searches only the title vector; Lyrics mode searches only the lyric
vector and excludes restricted entries unless the key has the exceptional restricted
lyrics scope.

When normal title full-text search has no result, permit one bounded `pg_trgm`
similarity fallback over the normalized title. Never broaden Lyrics mode. Order every
result by an accent-insensitive normalized title and then `song_uid`.

Use signed, opaque keyset continuations containing the snapshot UUID, normalized query,
mode, page size, search strategy, and final ordering key. A continuation is valid for 24
hours and remains pinned to a retained completed snapshot. Tampered or query-mismatched
state returns 400. Expired or pruned snapshot state returns 410 with a server-generated
restart URL.

Expose versioned Django Bolt resources for search, song metadata, and structured lyrics.
All response and error types are msgspec-backed Django Bolt `Serializer` classes in the
owning app's `schema.py`. Use hashed Bearer keys with explicit scopes. Coordinate fixed
one-minute rate windows in PostgreSQL so limits remain correct across API processes:
60 search or metadata requests and 30 lyric requests per key.

Publish OpenAPI JSON in every environment. Serve Swagger UI locally and ReDoc in
production from the same documentation entry point.

## Alternatives Considered

### Offset pagination against the active snapshot

Rejected because activation between requests can shift offsets, causing duplicate or
missing songs, and because deep offsets perform unnecessary scans.

### Client-decoded continuation parameters

Rejected because clients could couple themselves to ordering internals and could alter
snapshot or rights-sensitive query state.

### Combined title and lyric relevance

Rejected because it violates the explicit Title/Lyrics modes and makes lyric matches
distract from known-title discovery.

### In-process rate-limit counters

Rejected because each Bolt process or Cloud Run instance would enforce an independent
counter, allowing aggregate traffic above the documented per-key limit.

### External search service

Rejected until PostgreSQL measurements against the target catalog demonstrate a
shortfall.

## Consequences

- Catalog Import promotion includes complete search documents before pointer activation.
- Pagination survives catalog activation while its snapshot remains retained.
- Snapshot pruning intentionally invalidates continuations with a recoverable 410.
- Restricted lyric text cannot participate in ordinary Integration Client Lyrics search
  or structured-lyrics responses.
- The rate limiter adds one short PostgreSQL transaction per protected read request.
- Search configuration and extensions must exist before search-vector backfill and index
  creation during migration.
