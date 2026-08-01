# ADR-0006: Render a Rights-Safe Public Catalog with Reactivated

## Status

Accepted

## Date

2026-08-01

## Context

Catalog Visitors need public Title and Lyrics search, readable Song Detail, freshness,
and an approximate Projection Preview. The Integration Client API already exposes the
same catalog domain through Bearer credentials, but browser pages have different input,
pagination, presentation, and authentication concerns. In particular, public search
accepts 1–128 characters, shows hints for empty input, defaults to 20 results, and caps
pages at 50.

Lyrics Rights Status is also a non-disclosure boundary. Approved and unknown entries
may expose cleaned lyrics and projection slides; restricted entries must be
metadata-only. Hiding lyric elements in the browser would still serialize restricted
content into the page source.

Projection Preview needs enough fidelity to assess line breaks and slide flow without
becoming a presentation controller or promising pixel-identical EasyWorship output.

## Decision

Serve public catalog pages from Django views and Reactivated template contracts. The
views call the same transport-neutral catalog search and active-entry services used by
Django Bolt handlers; browser pages never call the Integration Client API. Keep public
input and page-size validation in a browser-presentation service while leaving the
underlying search, ordering, rights filtering, and signed snapshot continuations shared.

Convert API-owned continuation tokens into named public URLs without decoding their
signed state. Empty input resolves Catalog Freshness and guidance without executing a
catalog-wide search. A pruned or expired continuation returns 410 with a named public
restart URL; malformed or mismatched state returns 400.

Project model entries into explicit presentation types before constructing Reactivated
props. For restricted entries, construct no lyric preview, cleaned lyric, section, or
slide props. Render metadata-only search and detail states from the remaining safe
fields.

Render eligible lyrics as ordered Song Sections and flatten their source-ordered slides
for a client-side Projection Preview. The preview uses a responsive 16:9 CSS canvas,
song-normalized text fitting, stable motion layers, native buttons, announced current
slide state, and a reduced-motion fallback. React owns only the current slide index;
Django continues to own routing, validation, permissions, and content selection. Do not
add a projection JSON endpoint.

## Alternatives Considered

### Fetch browser pages through the Integration Client API

Rejected because public visitors do not have Bearer credentials and because it would
couple rendered UI to a machine transport with different query limits, empty-state
behavior, scopes, errors, and rate limits.

### Serialize all lyrics and hide restricted content in React

Rejected because restricted lyrics would remain recoverable from preloaded props, page
source, caches, and browser tooling.

### Add a video background asset for Projection Preview

Rejected for V1 because an additional media asset and playback lifecycle are not needed
to approximate continuous motion. CSS motion stays uninterrupted across slide changes,
is naturally muted, and has a deterministic reduced-motion state.

### Reproduce EasyWorship rendering exactly

Rejected because available source evidence does not completely resolve presentation
formatting, and the product requirement is an operational approximation rather than a
presentation controller.

## Consequences

- Public and Integration Client transports share catalog behavior without calling one
  another.
- Restricted lyric content is absent from both rendered HTML and preloaded props.
- Browser-specific validation can remain tighter than API validation without forking
  PostgreSQL search behavior.
- Public pagination remains stable across catalog activation while its snapshot is
  retained.
- Projection interaction hydrates in React while its first slide remains server
  rendered and keyboard accessible.
- Future visual improvements may use retained source evidence, but a pixel-identical
  renderer or presentation-control behavior requires a separate decision.
