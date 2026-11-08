# ADR-0016: Share Schedule Previews as Snapshots

## Status

Accepted

## Date

2026-11-08

## Context

The Technical Team prepares the service in EasyWorship on a Windows machine.
The choir needs to review that preparation without access to the machine. The
Song Catalog reflects the library; it cannot reproduce the changes made for a
particular service, such as a repeated chorus or a different slide break.
[EasyWorship's song editing guide](https://support.easyworship.com/support/solutions/articles/24000020402-adding-and-editing-songs)
describes how edits can be saved to the schedule alone.

## Decision

Accept ordered songs and their explicit slide lines from a scoped Integration
Client. Store the submitted content and expiry, and render the page on demand
using the existing Projection Preview. EasyWorship remains the source of the
prepared slides; the platform supplies its own 16:9 projection style. The preview
does not read or modify the Song Catalog, and there is no saved HTML or media.

The unlisted link grants read access without an account. The Technical Team
publishes only lyrics cleared for sharing with anyone who has the link. The
publishing key is distinct from catalog access; catalog permissions do not grant
permission to publish, and the preview does not fetch restricted catalog lyrics.

Each publish creates a new link. Earlier previews remain as published until their
original expiry. A single server setting controls the lifetime of new previews,
defaulting to 72 hours.

Referencing catalog IDs would avoid duplicating text, but it would lose the
service-specific slide arrangement and let later catalog changes affect the
review. Saving rendered pages or screenshots would preserve more visual detail
at the cost of handling media from the presentation machine.
