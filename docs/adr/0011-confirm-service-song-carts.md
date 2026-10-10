# ADR-0011: Confirm Service Song Carts Outside the Song Catalog

## Status

Superseded by [ADR-0012](0012-prepare-service-song-carts-with-optional-formatting.md).
Retained as the record of the earlier implementation choices.

## Date

2026-10-09

## Context

Users need to collect catalog songs for a dated church service, group them into
Call to Worship and Praise & Worship, and notify administrators at checkout.
Services can occur on Sundays or other days. This expands the catalog-only runtime
scope in ADR-0001; it does not restore the archived scheduling or inbound-song apps.

Catalog snapshots may be replaced and pruned. A confirmed selection must remain
readable after those changes. Notification failures must not discard that selection
or lead repeated checkout requests to create repeated confirmations.

## Decision

Add `song_carts` as the owner of service song selection. The first version uses
existing signed-in accounts, one personal cart per user and service date, and the
two named Service Sections. Account invitations remain unchanged. Drafts support
adding and removing songs; confirmed carts are read-only. A song may appear once
per section, including in both sections. Songs retain their order of addition.

Store stable song IDs and selected titles/authors without foreign keys to catalog
entries or copied lyrics. The Song Catalog and EasyWorship Library remain read-only
to this workflow. Adding a song resolves the active catalog through its public
metadata service; rendering a saved cart uses its retained metadata.

Use Django forms and Reactivated pages with CSRF-protected POST mutations. Public
service functions enforce ownership and lock the cart while changing or confirming
it. No new JSON interface is needed. Keep the new tables behind the existing Django
authorization boundary, including RLS and rejection of Supabase API roles.

Email active staff administrators after the confirmation transaction commits, using
the existing email integration. Store pending/sent/failed notification status;
administrators can retry failed or pending emails from the admin portal. Successful
notifications and repeated checkout are idempotent. Local development uses console
email so checkout cannot contact the SMTP service configured in `.env`.

## Alternatives Considered

### Reference immutable Catalog Entries directly

Rejected because cart history would prevent pruning or disappear with a snapshot.
Selected metadata records the user's selection independently of imports.

### Roll back checkout when email fails

Rejected because the selection is valuable even when SMTP is unavailable, and a
network error can occur after a provider accepts a message. Confirmation and
notification status are recorded separately.

### Add a background queue and WhatsApp integration immediately

Deferred for this first version. Existing email delivery satisfies administrator
notification without introducing a queue or selecting a WhatsApp provider and group
destination. There is no automatic retry worker or guarantee of exactly-once email
delivery if a provider accepts a message before an interrupted status update.

## Consequences

- This partially supersedes ADR-0001's exclusion of service planning from the runtime.
- Existing invitations govern who can prepare carts; a new choir account role is
  outside this change.
- Carts belong to individual users, rather than being shared service plans.
- Checkout records the requested songs; it does not indicate administrator approval
  or change EasyWorship content.
- Confirmed selections cannot be amended in this version.
- Deployment needs the new Django migration. Email recipients are active staff
  accounts; production uses the existing SMTP configuration.
