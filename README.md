# Worship Prep Platform

Worship Prep Platform provides a public, read-only Song Catalog sourced from the
church's EasyWorship Library and personal song carts for service preparation. The
EasyWorship Library remains authoritative; the platform ingests immutable snapshots
without writing back to the source.

This stacked branch contains the complete six-slice Song Catalog pivot: the greenfield
foundation, the portable
[Catalog Exporter](exporter/), the versioned
[Catalog Import Package contract](contracts/catalog-import/v1/), immutable Catalog
Importer snapshots, PostgreSQL search, and the Integration Client read API. Public
Song Catalog search, Song Detail, and Projection Preview are also available without an
account. Audited Catalog Administration, Windows delivery and scheduling, recovery,
rollback, alerts, and automated release gates complete the final slice tracked by
GitHub issue #21.

## Quick Start

Install Python and JavaScript dependencies, then run the Django application:

```bash
uv sync --group local
npm ci --legacy-peer-deps
poe migrate
poe dev
```

Catalog imports and search require PostgreSQL; configure `DATABASE_URL` before applying
migrations or running the API locally. Local automated tests boot a disposable
PostgreSQL 16 database through Testcontainers, so Docker must be running. GitHub Actions
uses its native PostgreSQL service container instead.

The application uses `public` as its only production schema. The regenerated
first-party migrations require a fresh application database; see
[ADR-0010](docs/adr/0010-rebuild-application-in-public.md) for the reset boundary.

```bash
poe test
```

## Local invitation and email testing

Start the development inbox and open http://localhost:8025:

```bash
docker compose -f docker/docker-compose.yml up -d mailpit
```

For a Django server running on the host, set these values in your local `.env`
and restart `poe dev`:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=127.0.0.1
EMAIL_PORT=1025
EMAIL_USE_TLS=false
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

The Compose Django and Bolt services already use Mailpit. Local mode otherwise keeps
email in the terminal. Mailpit captures mail for every recipient in one browser inbox
without delivering it externally, so no real recipient accounts are needed. Its SMTP
and inbox ports are bound to localhost. Captured messages disappear when the container
is recreated. Production continues to use its SMTP provider.
Invitation emails include branded HTML, a plain-text alternative, and an acceptance
link to the account setup form.

Use a local database for this exercise. Create an initial Superuser with
`poe manage createsuperuser` if needed, then test each role with a different email:

1. Sign out and request an invitation from the sign-in page. In Mailpit, confirm that
   active staff receive the review notification. For its review link, set the Django
   Site domain to the local app address (for `poe dev`, `localhost:8001`).
2. Sign in as a Superuser. In **Invitation requests**, select the request and choose
   **Approve and invite as Member** or **Approve and invite as Catalog Administrator**.
3. Open the invitation email in Mailpit. Sign out before following its acceptance link
   and completing signup. Members can search, add catalog or unlisted songs, and submit
   their own song carts. They see no Admin link, and `/admin/` requires staff access.
4. Repeat with the other role. Catalog Administrators receive staff access and can
   inspect submissions and catalog administration. Invitation approval and user
   management remain Superuser-only. Submission acknowledgement and replies additionally
   require membership in the **Technical Team** group.

Public requests always start as **Member**; the requester cannot select staff access.
To invite someone directly, a Superuser opens **Invitations → Add invitation**, enters
their email, and chooses **Member** (the default) or **Catalog Administrator** before
saving. The selected role is recorded with the invitation and applied after signup;
Catalog Administrators do not receive Superuser privileges or invitation management.

Focused regression checks cover emailed acceptance links, signup role assignment,
admin access, and song preparation/submission:

```bash
poe test apps/accounts apps/song_carts
```

## Foundation Modules

- `apps.accounts`: custom user identity, invitation requests, sign-in, and invitation
  administration.
- `apps.api_keys`: hashed Integration Client credentials, target Song Catalog scopes,
  rotation, revocation, database-coordinated rate limits, and administration.
- `apps.catalog`: immutable Song Catalog snapshots, import processing, search, signed
  continuations, rights-aware reads, audited Lyrics Rights Provenance, recovery,
  rollback, and failure alerts.
- `apps.song_carts`: personal dated song selections, submission history, owner
  comments, Technical Team acknowledgement, and email delivery records.
- `apps.common`: shared Django infrastructure, model utilities, middleware, and
  Reactivated context.

The archived schedule, content-submission, and inbound-song product is available at
tag `archive/pre-song-catalog-pivot`; it is intentionally absent from the active
runtime and migrations.

## HTTP Architecture

- Django Bolt serves product and machine-facing JSON APIs from each app's `api.py`.
- Each app defines its msgspec-backed Django Bolt request and response types in
  `schema.py`; handlers construct those contracts rather than ad hoc dictionaries.
- Django views and Reactivated templates serve rendered product UI.
- Transport-neutral services hold reusable domain and application behavior.
- Django's standard stack continues to own operational and framework routes such as
  health/readiness, admin, invitations, and authentication callbacks.

See [ADR-0004](docs/adr/0004-separate-json-and-rendered-transports.md) for the boundary,
rationale, and review rule.

## Integration Client API

The versioned API is served under `/api/v1/` with Bearer-key scopes:

- `GET /api/v1/catalog/search` requires `catalog.search`; Lyrics mode also requires
  `catalog.lyrics.read`.
- `GET /api/v1/catalog/songs/{song_uid}` requires `catalog.song.read`.
- `GET /api/v1/catalog/songs/{song_uid}/lyrics` requires `catalog.lyrics.read`, plus
  `catalog.lyrics.restricted` for restricted lyrics.
- `POST /api/v1/catalog/imports` requires `catalog.import`; the Catalog Exporter may
  attach its durable event timeline and scheduled/manual trigger identity.

Machine-readable OpenAPI is available at `/api/v1/docs/openapi.json`. Local development
serves Swagger UI at `/api/v1/docs`; production serves ReDoc at the same entry point.
Search continuations are opaque server-provided URLs and expire after 24 hours.

## Public Song Catalog

The root route serves the public Song Catalog through Django and Reactivated. Visitors
can search titles or lyrics, follow snapshot-pinned result continuations, and open
rights-aware Song Detail pages. Approved and unknown entries include structured lyrics
and an accessible approximate 16:9 Projection Preview; restricted entries remain
metadata-only. Empty search input shows guidance rather than dumping the catalog.

Rendered pages reuse the transport-neutral catalog search/read services directly. They
do not call the Integration Client API, and restricted lyric fields are removed before
the Reactivated props are serialized. See
[ADR-0006](docs/adr/0006-public-catalog-presentation.md).

## Service Song Carts

Signed-in users can add catalog songs to a personal cart for any service date from
search results or Song Detail. The fixed sections are Call to Worship, Praise, and
Worship. Drafts allow song removal. Submitting locks the selection as Pending,
emails the owner a receipt, and notifies active staff in the `Technical Team` Django
group. The **My submissions** page includes owned drafts and past submissions with
state filters and sorting.

The Unfold admin home shows a Pending queue and submitted counts, excluding drafts.
General staff can inspect all selections; Technical Team members acknowledge, reject,
and reply. Opening a visible Pending admin detail records one Confirmed acknowledgement
through a CSRF-protected POST and emails the owner. Confirmed means seen by the team.
Rejection requires a reason and preserves any previous acknowledgement.

Each selection has one owner comment thread. Comments stay editable in Draft, then
for 15 minutes after submission or posting; later changes use a follow-up comment.
Admins read the thread and compose email responses rather than posting comments.
Each email has its own delivery outcome and manual retry. Local mode previews email
in the application terminal or the development inbox described above; production uses
the existing SMTP configuration.

Assign active staff reviewers to `Technical Team` using the superuser-managed Users
admin. Configure the Django Site domain for links in notification emails. Migration
0002 converts older owner-confirmed selections to Pending without resending email,
and maps the former combined Praise & Worship section to Praise. See
[ADR-0013](docs/adr/0013-acknowledge-song-submissions-and-communicate-by-email.md).
Users can add unlisted songs with a title and pasted lyrics, save a local projection
preview, and mark the prepared lyrics reviewed before submission. Draft edits clear
review; submitted lyrics stay locked. Original and prepared lyrics remain in the
selection, with formatted text available to the Technical Team in admin and email.
No catalog entry or external formatting call is made. See the
[intake flow](docs/design/unlisted-song-intake.md). Reordering and optional external
formatters remain separate work.

### Follow-up work

- [Draft song reordering in cart and admin](https://github.com/nicksspirit/worship-prep-platform/issues/57).
- [Optional n8n or replacement lyrics formatter](https://github.com/nicksspirit/worship-prep-platform/issues/58).
- [WhatsApp Technical Team notifications](https://github.com/nicksspirit/worship-prep-platform/issues/59), pending provider and destination decisions.
- [Real SMTP verification](https://github.com/nicksspirit/worship-prep-platform/issues/60), using controlled recipients.

## Catalog Administration and Automation

Invited Catalog Administrators can inspect Catalog Import Runs, exporter/importer event
timelines, retained snapshots, and Lyrics Rights Provenance. Superusers alone change
rights with policy-valid evidence, recover a retained failed package, roll back the
active pointer, manage invitations, and issue, rotate, or revoke Integration Client
keys.

The stable Windows installer is available from `/install` for a one-line Windows PowerShell
install. It verifies the latest `exporter/v*` binary, protects the import key with
current-user DPAPI, and schedules the Catalog Exporter weekly at 3:00 AM
America/Los_Angeles with one retry after 30 minutes. See
[ADR-0007](docs/adr/0007-audit-and-automate-catalog-operations.md) and the
[Catalog Exporter guide](exporter/README.md).

## Commands

Project commands are Poe aliases over Django management commands:

```bash
poe --help
poe manage --help
poe makemig
poe migrate
poe test
```

## Frontend asset pipeline

`client/` contains React and TypeScript source. `static/` contains hand-authored files
served at `/static/`, such as icons, installer scripts, and product media. `npm exec
build.client` compiles the React bundle into the generated `static/dist/` directory.
Then Django's `collectstatic` gathers both sources into the generated `public/static/`
deployment directory. Neither generated directory is committed.

See [deployment documentation](docs/deploy.md) for Cloud Run, Supabase PostgreSQL,
and private Supabase Object Storage setup. Architectural decisions live in
`docs/adr/`; the approved domain vocabulary and product contract are in issue #21.
