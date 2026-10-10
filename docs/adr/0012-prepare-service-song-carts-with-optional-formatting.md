# ADR-0012: Prepare Service Song Carts with Optional Formatting

## Status

Partially implemented: three sections and local unlisted intake are available;
draft reordering and external formatter adapters remain pending. Supersedes ADR-0011's product scope,
section choices, and notification recipients. ADR-0013 supersedes its confirmation,
per-song notes, and recipient decisions.

The [implemented intake flow](../design/unlisted-song-intake.md) uses required title
and lyrics, one submission comment thread, and explicit review of saved content
before checkout. Draft edits invalidate review; stale preview approvals are rejected.

## Date

2026-10-09

## Context

Users confirmed three service sections: Call to Worship, Praise, and Worship.
They need to select catalog songs, supply unlisted songs, review projection content,
and make a final submission to the Technical Team. They also want basic functionality
available before introducing n8n or another formatting integration.

## Decision

Retain personal carts keyed by owner and service date and their selected-song items.
Section choices are fixed values, not a separate configuration model. Catalog items
use the submission's comment thread for instructions; unlisted songs require title
and pasted lyrics. Unlisted
songs belong to the selection and do not create imported catalog entries.

Keep original lyrics and the reviewed prepared content with the item. Use the existing
projection presentation and agreed initial rules of 45-character wrapping and two
lyric lines per slide, preserving words and order. Derive formatted text handoff from
the reviewed result. The app preview does not guarantee identical EasyWorship display.

Use one small lyrics preparation interface with a local implementation. An optional
adapter can call n8n or another formatter and return the same prepared-content shape.
Without that adapter configured, make no external formatting call. Django owns
validation, authorization, persistence, and submission. Formatters do not write the
application database or submit selections. No general pipeline engine is needed.

Checkout locks the final selection, attributed to its owner and date, and then emails
active staff members of the Technical Team Django group. Submission and notification
outcomes remain
separate. Repeat submission must not create another confirmation. Retain manual email
retry initially. Preserve existing transport and database access restrictions.

User clarification on 2026-10-10: addition order is the default, but songs can be
reordered in the UI using drag and drop and in the admin panel. Persist section-local
positions on existing items and use the same domain operation for both interfaces.
Both user and administrator reordering are limited to drafts, as confirmed on
2026-10-10. Submitted order stays frozen with the reviewed handoff.

Retain reviewed content independently of later imports. Catalog entries without
available previews may be selected as metadata-only items; the Technical Team can
look them up by title in EasyWorship. Empty sections are valid; an empty cart cannot
be submitted. The email includes date, submitter, ordered songs, comments, and available
formatted lyric text so the team can work without a new application account.

## Alternatives Considered

- Requiring n8n for all previews would block the core experience when it is absent.
- Restoring the archived scheduling/intake product would add functionality outside
  this workflow and couples formatting to persistence.
- A plugin framework or pipeline graph is unnecessary for one replaceable formatter.
- Writing directly to EasyWorship or creating a native import artifact exceeds the
  agreed formatted-text handoff.

## Consequences

- Deliver the core workflow first; add the external formatter independently later.
- Editing draft lyrics invalidates their previous preview; final submission uses the
  reviewed result, without another formatter call.
- External formatter failures retain draft input and cannot masquerade as successful
  preparation; users retry or deliberately review local preparation.
- Submitted carts cannot be amended in the initial version.
- User and admin reordering enforce the same draft-only rule.
- Email retries are manual; there is no exactly-once delivery guarantee.
- Team email configuration and actual projector compatibility still need verification.

See [the user flow and storage design](../design/song-cart-flow.md).
