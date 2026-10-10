# ADR-0013: Acknowledge Song Submissions and Communicate by Email

## Status

Accepted and implemented. Supersedes ADR-0012's submission
confirmation, per-song notes, and team recipient choices; other preparation
decisions remain applicable.

## Date

2026-10-10

## Context

Users need ownership-scoped submission history and the Technical Team needs an
Unfold overview. User submission and team acknowledgement are different events.
The team responds by email rather than participating in an application chat.

## Decision

Reuse the existing dated cart record: Draft → Pending on owner submission;
Pending → Confirmed when an active staff Technical Team group member first opens
the visible admin details. Confirmation means seen, not projection-ready. Use an
atomic, CSRF-protected POST acknowledgement after rendering; GET stays read-only.
Record reviewer/time and send one confirmation email. Pending or Confirmed can
be Rejected with a reason; preserve earlier acknowledgement and email history.

Freeze submitted song content. Keep one owner-authored comment thread per
submission, with no song-level comment records. Song references are plain text.
Allow a 15-minute edit window, then follow-up comments. Team replies are single
emails composed in admin and never inserted into the thread. Track lifecycle,
comment, and manual-reply deliveries separately so failures remain retryable
without undoing saved state. Team messages target active group members.

## Alternatives Considered

- User checkout marking Confirmed hides the distinction between submission and
  acknowledgement.
- Confirmation as projection readiness promises more than opening details proves.
- Mutating GET could acknowledge on a prefetch or incidental request.
- Per-song threads and admin chat add complexity beyond the agreed communication.

## Consequences

- Legacy owner-confirmed carts become Pending without notification replay.
- Email acceptance does not guarantee inbox delivery; retries remain manual.
- Unfold native dashboard and detail extensions suffice; no custom AdminSite.
- See [the implementation design](../design/submission-management.md).
