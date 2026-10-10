# Song Submission Management

## Status

Design accepted for implementation on 2026-10-10 (user: “Alright let's proceed”).
This extends the existing song-cart design; it does not
replace the agreed three service sections, preview, or optional formatter. The user
has renamed preparation notes to comments and added ongoing comment communication.

## Requirements Confirmed by the User

- A selection belongs to the user who created its cart.
- User submission moves Draft to Pending. Confirmation acknowledges that an
  authorized Technical Team member has seen the submission by opening its admin
  detail page. It does not mean songs are ready for projection.
- Technical Team authority comes from membership in a Django group. General staff
  status alone does not establish membership in that team.
- Record the first confirming team member and time. Subsequent views do not create
  additional confirmations or confirmation emails.
- On submission, show a received message and email the submitter a receipt. Notify
  the Technical Team of the new submission. When the team first opens the details,
  send the submitter a separate confirmation email.
- Pending and Confirmed selections keep their songs, date, order, and prepared
  content locked. Users can communicate requested changes through comments.
- There is one comment thread per submission and no per-song comments, notes, or
  comment attachments. A user can reference a specific selected song's ID in the
  comment text. Show a stable reference alongside each selected song.
- Users can add comments before or after submission and edit posted comments during
  a limited time window. Once the window expires, add a follow-up comment instead.
- Only the submission owner posts comments. Administrators read the full submission
  and its comments and send an email response; they do not post in the thread.
- Receipt, first-view confirmation, and rejection messages are automated. A manual
  admin email can address the whole submission and its comments in one response.
- Rejection can apply to Pending or Confirmed submissions, with a required reason
  and an automated rejection email. Preserve the earlier first-view acknowledgement.
- Signed-in users land on Song Catalog search.
- Add a visible navigation item opening the user's submissions page.
- Use a simple table showing that user's drafts and submitted selections, including
  previous service dates, with state filters and sorting.
- Administrators can review submissions from different users. The Unfold admin home
  should give a quick overview of submitted selections and their submitters.
- Drafts are accessible to administrators but hidden by default and excluded from
  submitted counts. Pending is the default admin queue.
- Design first, then delegate implementation to sub-agents.
- The orchestrator conducts an end-to-end browser walkthrough with a signed-in
  ordinary user and an administrator. Two adversarial agents independently review
  it: one checks workflow and technical behavior; the other must load Impeccable
  and review both user and admin UI against existing styling and accessibility.

## Previous Behavior Replaced

Previously user checkout set `confirmed` and `confirmed_at`; the admin is read-only.
The existing user cart list shows only Draft/Confirmed without state filters.
Email delivery already has its own Pending/Sent/Failed status. Keep that distinction:
a Pending submission is awaiting administrator confirmation, not email delivery.
Past service dates are a date attribute/filter, not a fourth submission state.

Default login previously redirected to `/admin/`, including ordinary users. The
required routing is ordinary user → Song Catalog search and administrator → admin
overview. Preserve explicit safe `next` destinations during login.

The new lifecycle changes the submission semantics recorded in ADR-0012. Keep that
record intact and capture the replacement in a new ADR once the design is agreed.

## Unfold and Access Facts

The installed Unfold 0.71.0 supports a dashboard callback and an admin index
template override; a custom AdminSite is unnecessary. Reuse the existing cart
changelist filters, search, and read-only selected-song details for review.
Current administrator access is active staff; the existing cart admin allows these
users to view all carts and retry notification. New automatic confirmation requires
Technical Team group membership, separate from staff access to admin.

Team reviewers need active accounts, staff access, and team group membership.
The custom UserAdmin currently omits its existing groups field; expose that field
through the established superuser-managed account admin when provisioning the team.
Unfold provides an extension outside the detail form and admin-protected custom
URLs, so automatic acknowledgement can use a small CSRF-protected POST once the
detail page is visible. An acknowledgement failure needs a visible retry control.
Only Pending → Confirmed is automatic: a delayed request must never overwrite a
Rejected state, and repeated views must never send another confirmation email.

Sources inspected locally: `backend/settings/components/auth.py`,
`backend/settings/components/admin_unfold.py`, `apps/accounts/views.py`,
`apps/song_carts/admin.py`, and installed `unfold/sites.py`/admin templates.

## Storage and Transport

Reuse the existing cart and song-item records. Add Pending and Rejected to the selection's state
and separate the submission timestamp from the administrator confirmation timestamp
and actor. Do not create a duplicate Submission model or copy songs between tables.
Keep ownership, date uniqueness, and existing service/transport boundaries.
Store owner-authored comments against the existing selection only. Do not add a
selected-song foreign key or song-level note field. A song reference in comment
text is plain text. A comment requests a change; it does not mutate the frozen song
selection or reset confirmation automatically. Manual admin emails have their own
delivery record and are not inserted into the user comment thread.

This replaces ADR-0012's per-song notes and required unlisted-song notes. An
unlisted-song form still requires title and lyrics; any preparation instructions
belong in the submission's comment thread. The initial submission comment is optional. Unlisted-song intake and optional formatting remain separate delivery
work; this implementation adds submission management to existing catalog carts.

## Rejection After Confirmation

Allow Pending → Rejected and Confirmed → Rejected. Confirmation means seen; the
team can discover a preparation problem after that acknowledgement. Require a
reason and send a new rejection email with that reason and the submission link.
The confirmation email must acknowledge seeing the selection without promising
that it is approved or ready for projection.

Retain the first confirmation actor/time and add rejection actor/time/reason.
Show the current Rejected state and the earlier acknowledgement in the submission
details. Do not erase or rewrite the earlier email. Opening Rejected details never
automatically confirms them again; duplicate rejection requests do not resend mail.
The songs remain locked and the user can add a comment asking for clarification.
Reopening is outside this initial version; the owner contacts the team through
comments and the team responds by email.

## Implementation Defaults

- Owners can edit posted comments for 15 minutes, enforced by the server. Draft
  comments remain editable; their window begins at submission if created earlier.
- New or edited comments on submitted selections notify active Technical Team
  group members. Comment emails do not change the submission state.
- An administrator composes one email response in the admin detail page. The reply
  is sent to the owner and recorded as an email delivery, not as a thread comment.
- Technical Team notification recipients are active staff members of the Django
  group named `Technical Team`, replacing the earlier configured team address.
- User table defaults to all owned selections, newest service date first. Columns:
  service date, song count, state, submission time, and open action. State filters
  include Draft/Pending/Confirmed/Rejected; sorting includes both service-date
  directions and most recently submitted.
- Admin home defaults to Pending with submitter, service date, song count,
  submission time, state and detail action; submitted totals exclude Drafts.
- Expose group assignment in the existing superuser-only account admin. General
  staff can inspect selections, but only team members acknowledge/reject/reply.
- Migrate legacy Confirmed to Pending, move checkout time into submitted_at,
  preserve existing notification outcomes and songs, and send no migration email.
- Change combined legacy Praise & Worship selections to Praise; new choices are
  Call to Worship, Praise, and Worship. Original song metadata remains intact.
- No worker, external formatting integration, unlisted intake, or reorder UI is
  added in this submission-management change.

The visible detail page acknowledges Pending submissions with an atomic,
idempotent CSRF-protected POST. Lists, Draft details, hidden pages, and GET requests
do not confirm a submission. A failed acknowledgement offers a visible retry.

A purpose-specific email record captures each message's recipients, content, and
individual delivery outcome. Email runs after transaction commit and can be retried
manually; it has no automatic worker. Legacy notification outcomes remain recorded
without inventing historical receipt or confirmation messages.

## Accepted Design

Ownership, state transitions, rejection history, comment editing, group management,
table defaults, and migration behavior are settled in the implementation defaults
above. Broader song preparation features remain in the original cart design.

## Delivery and Review Plan

1. Record the accepted design and domain terms.
2. Delegate bounded user UI and Unfold admin UI work against agreed contracts;
   coordinate shared persistence, services, class-based views, and migrations.
3. Run the authorized end-to-end walkthrough using local accounts and console email.
   Coordinate reviewer browser access so they do not navigate a shared tab at once.
4. Fix actionable functional and Impeccable findings, then repeat affected steps.

Functional review includes ownership isolation, Draft → Pending → Confirmed,
method/CSRF protections, repeated actions, filtered lists, and notification failure.
Visual review includes search, cart, submission list/detail, admin home/review,
desktop/mobile presentation, contrast, keyboard access, and state/empty/error copy.

## Verification — 2026-10-10

- Local PostgreSQL migration applied; Django system checks and migration drift check
  passed. Reactivated contracts generated and TypeScript passed.
- Combined song-cart, account foundation, and catalog suite: 180 tests and 11 subtests
  passed.
- Orchestrator and independent functional reviewer exercised sign-in, catalog add,
  draft comments, submission, filters, automatic team acknowledgement, repeated
  views, email reply, rejection, and retained acknowledgement history.
- Independent Impeccable reviewer checked user/admin desktop and 390px layouts,
  including owner follow-up comments on Rejected and a retained Draft. Fixed mobile
  filter truncation and dark admin link contrast. Functional review also restored
  visible stable song references in the admin.
- Email used the console backend. Real inbox delivery, physical devices, and screen
  readers were not checked. Impeccable's automated detector was unavailable; visual
  review used browser screenshots and computed styles.
