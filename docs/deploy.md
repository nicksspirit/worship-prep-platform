# Deploying Worship Prep Platform

This document explains how to deploy the application to Google Cloud Run.

It is written for a human operator, not for CI. Every command you need is included. If you follow the steps in order, you should be able to reproduce the production deployment from a clean machine.

## What This Deployment Creates

This repository deploys three Cloud Run resources:

- `wpp-app`: the Django web application
- `wpp-api`: the Django-Bolt API service
- `wpp-migrate`: a Cloud Run Job that runs Django migrations

The `prod` Docker target contains Python and is shared by the app, migrations,
and Bolt. The API service has two containers: `bolt` runs that image, and its
ingress runs the `ingress` target based on the official Nginx image:

- `wpp-app` runs `deploy/start-django.sh` (Gunicorn only)
- `wpp-api` runs `deploy/start-bolt.sh` in the Bolt container and the official
  Nginx entrypoint in its ingress container
- `wpp-migrate` runs `deploy/start-migrate.sh`

## Assumptions

This guide assumes all of the following are true:

- You are deploying from the root of this repository.
- You have access to the Google Cloud project you want to deploy into.
- You have permission to create and update:
  - Cloud Run services and jobs
  - Secret Manager secrets
  - Artifact Registry repositories
  - service accounts and IAM bindings
- You have a Supabase project already created.
- You have a Google OAuth client already created.
- You are comfortable copying and editing environment variable values.
- You are using the current deployment naming:
  - Django service: `wpp-app`
  - Bolt service: `wpp-api`
  - migration job: `wpp-migrate`

This guide also assumes the following current production choices:

- Google Cloud project: `worship-prep-portal`
- Google Cloud region: `us-west1`
- Artifact Registry repository: `worship-prep`
- runtime service account name: `wpp-runtime`
- image name: `worship-prep-app`
- Supabase storage bucket for uploads: `wpp-media`
- Supabase S3 endpoint format: `https://<SUPABASE_PROJECT_REF>.supabase.co/storage/v1/s3`

## Architecture Overview

At a high level, deployment works like this:

1. Cloud Build builds and pushes the `prod` and `ingress` targets.
2. Cloud Build deploys and executes `wpp-migrate` with the `prod` image.
3. Cloud Build deploys `wpp-api` with the Python backend and Nginx ingress images.
4. Cloud Build deploys `wpp-app` with the `prod` image.

`app.rccgcm.org` serves Django pages directly through Gunicorn on `PORT` (8080 in
Cloud Run). The app has no Nginx process, API proxy, or Bolt upstream URL.
`api.rccgcm.org` serves the Bolt API independently. Both services retain public
Cloud Run access and 600-second request timeouts. Protected API routes enforce
Integration Client authentication and scopes.

The Windows exporter downloads its installer from `app.rccgcm.org/install`, but
uploads directly to `https://api.rccgcm.org/api/v1/catalog/imports`.
`CATALOG_EXPORTER_API_URL` configures that API origin for another environment.
Existing Windows installations must be reinstalled during the rollout:
older scheduled tasks still target the app domain and will receive 404 after the
proxy is removed, until reinstallation updates their endpoint. See [the reinstall procedure](windows-catalog-exporter.md).

Only the API ingress container enables HTTP/2. Cloud Run terminates TLS and forwards h2c
to Nginx on port 8080; locked Bolt 0.12.0 serves HTTP/1 on port 8000 in the
same instance network. Nginx permits a 130 MiB multipart request while the importer retains its 128 MiB package and 1 MiB event
limits. The app uses HTTP/1 between Cloud Run and Gunicorn; external browser TLS
is still terminated by Cloud Run. See [HTTP/2 verification](http2-catalog-imports.md).

Both services use HTTP startup probes. Cloud Run first starts Bolt and checks
`/api/v1/docs` on port 8000. Only after that probe succeeds does its startup
dependency permit Nginx to start. The ingress probe checks the same route on
port 8080 through Nginx and Bolt before traffic is admitted. The app checks
`/health/` directly through Gunicorn. The API check uses an
existing public route that proves the actual Bolt application has loaded; there
is no `/api/v1/health` or `/api/v1/ready` route. Probes use HTTP/1 (which Nginx also
accepts) every two seconds, with a two-second timeout and 60 attempts. Cloud Run
holds traffic until the probe succeeds and shuts down an instance that never
becomes ready within that startup window. These startup checks do not test the
availability of the database or storage; Django's `/ready/` checks those separately.

Gunicorn runs as the app container's main process and drains requests for up to
eight seconds on SIGTERM. Bolt runs as its container's main process with an
eight-second graceful shutdown timeout. The ingress uses a small `/bin/sh`
launcher that calls the official Nginx entrypoint and waits for its child. It
converts Cloud Run's SIGTERM to Nginx SIGQUIT so active requests can drain, with
`worker_shutdown_timeout 8s` leaving room within Cloud Run's ten-second shutdown
window. Cloud Run manages startup and both container lifecycles; Tini is not
needed. Long-running imports can still be interrupted at shutdown. An interrupted exporter retains
its outbox package and retries with the same run identity.

The API service declaration lives in `deploy/api-service.json.template`. Cloud
Build inserts JSON-escaped settings and Secret Manager references and replaces
the full container list, so migrating the old unnamed container cannot leave an
extra server behind. It then ensures the public invoker IAM grant. The manifest
sets the API maximum to 20 instances, matching the existing service, and allocates
one CPU each to Bolt and Nginx; two containers increase per-instance resources.

After deployment, check the API route without credentials or imported data:

```bash
curl -i -X OPTIONS https://api.rccgcm.org/api/v1/catalog/imports
```

Expect HTTP 204 and `Allow: POST, OPTIONS`. Check `/admin/` and `/install` on the
app domain too. The former app-domain `/api/` route is intentionally absent.

The repo already contains the automation for this in:

- `cloudbuild.yaml`
- `deploy/deploy.sh`
- `deploy/setup-gcp.sh`
- `deploy/setup-supabase-storage.sh`

## Prerequisites

Install the following tools:

- Google Cloud SDK
- Supabase CLI
- Docker
- `uv`
- Node.js and npm

Check that each tool is installed:

```bash
gcloud --version
supabase --version
docker --version
uv --version
node --version
npm --version
```

Authenticate to Google Cloud:

```bash
gcloud auth login
```

Set the active Google Cloud project:

```bash
gcloud config set project worship-prep-portal
```

Confirm the active project:

```bash
gcloud config get-value project
```

You should see:

```text
worship-prep-portal
```

## Step 1: Prepare Local Environment Variables

Create a local `.env` file if you do not already have one:

```bash
cp .env.example .env
```

Edit `.env` and fill in all real values.

The important values are:

- `SECRET_KEY`
- `DATABASE_URL`
- `DIRECT_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SUPABASE_STORAGE_BUCKET`
- `SUPABASE_CATALOG_IMPORT_BUCKET`
- `SUPABASE_S3_ENDPOINT`
- `SUPABASE_S3_ACCESS_KEY`
- `SUPABASE_S3_SECRET_KEY`
- `SUPABASE_S3_REGION`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `SITE_ID`

The expected meaning of the database URLs is:

- `DATABASE_URL`: Supabase pooled connection, used by running services
- `DIRECT_URL`: Supabase direct `5432` connection, used only by migrations

The `worship-prep-portal` application uses `public` as its only application schema.
Both URLs must explicitly select it by including
this query parameter (append it with `&` when the URL already has a query string):

```text
options=-c%20search_path%3Dpublic
```

Encode the space as `%20` to preserve the intended connection option. See
[ADR-0010](adr/0010-rebuild-application-in-public.md) for the reset decision.
The regenerated first-party migrations require a fresh application database;
do not apply them to the previous migration history or use fake migrations.

The expected meaning of the storage variables is:

- `SUPABASE_STORAGE_BUCKET`: the media bucket name, usually `wpp-media`
- `SUPABASE_CATALOG_IMPORT_BUCKET`: the private package/report bucket, usually `wpp-catalog-imports`
- `SUPABASE_S3_ENDPOINT`: your Supabase S3 endpoint, in the form `https://<PROJECT_REF>.supabase.co/storage/v1/s3`
- `SUPABASE_S3_ACCESS_KEY`: S3 access key
- `SUPABASE_S3_SECRET_KEY`: S3 secret key
- `SUPABASE_S3_REGION`: usually `us-east-1`

The email values configure SMTP for invitation messages and scheduled Catalog Import
failure alerts. `EMAIL_HOST_PASSWORD` is stored in Secret Manager; the remaining SMTP
settings are passed as Cloud Run environment values.

**Important:** `deploy/deploy.sh` will hard-fail if `SUPABASE_STORAGE_BUCKET` or `SUPABASE_S3_ENDPOINT` are empty. Make sure both are set in `.env` or exported before running the script. If your `.env` only has `SUPABASE_URL`, you still need to add these two variables separately.

## Step 2: Create the Supabase Storage Buckets

The app expects a media bucket and also uses static asset handling during deployment.

Log in to Supabase if needed:

```bash
supabase login
```

Link the CLI to your project if needed:

```bash
supabase link --project-ref <SUPABASE_PROJECT_REF>
```

Create the media bucket:

```bash
export SUPABASE_BUCKET_NAME=wpp-media
./deploy/setup-supabase-storage.sh
```

Create the static bucket if you want it available as well:

```bash
export SUPABASE_BUCKET_NAME=wpp-static
./deploy/setup-supabase-storage.sh
```

If the bucket already exists, the script is safe to rerun.

## Step 3: Bootstrap Google Cloud Once

This step enables APIs, creates Artifact Registry if needed, creates the runtime service account if needed, and grants the minimum IAM roles expected by this deployment.

Run:

```bash
export GCP_PROJECT_ID=worship-prep-portal
export GCP_REGION=us-west1
export AR_REPOSITORY=worship-prep
export RUNTIME_SA_NAME=wpp-runtime
./deploy/setup-gcp.sh
```

What this script does:

- enables the required Google APIs
- creates the Artifact Registry Docker repository if missing
- creates the runtime service account if missing
- gives the runtime service account access to Secret Manager
- gives Cloud Build permission to deploy Cloud Run
- gives Cloud Build permission to act as the runtime service account
- gives Cloud Build permission to push images to Artifact Registry

## Step 4: Create Secret Manager Secrets

Cloud Build and Cloud Run expect the following secrets in Google Secret Manager:

- `DATABASE_URL`
- `DIRECT_URL`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SUPABASE_S3_ACCESS_KEY`
- `SUPABASE_S3_SECRET_KEY`
- `EMAIL_HOST_PASSWORD`

The safest workflow is:

1. source your local `.env`
2. create the secrets from those values
3. add a new version when values change later

Load your local `.env` into the shell:

```bash
set -a
source .env
set +a
```

Create each secret if it does not exist yet:

```bash
printf '%s' "$DATABASE_URL" | gcloud secrets create DATABASE_URL --data-file=-
printf '%s' "$DIRECT_URL" | gcloud secrets create DIRECT_URL --data-file=-
printf '%s' "$SECRET_KEY" | gcloud secrets create SECRET_KEY --data-file=-
printf '%s' "$GOOGLE_CLIENT_ID" | gcloud secrets create GOOGLE_CLIENT_ID --data-file=-
printf '%s' "$GOOGLE_CLIENT_SECRET" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=-
printf '%s' "$SUPABASE_S3_ACCESS_KEY" | gcloud secrets create SUPABASE_S3_ACCESS_KEY --data-file=-
printf '%s' "$SUPABASE_S3_SECRET_KEY" | gcloud secrets create SUPABASE_S3_SECRET_KEY --data-file=-
printf '%s' "$EMAIL_HOST_PASSWORD" | gcloud secrets create EMAIL_HOST_PASSWORD --data-file=-
```

If a secret already exists, add a new version instead:

```bash
printf '%s' "$DATABASE_URL" | gcloud secrets versions add DATABASE_URL --data-file=-
printf '%s' "$DIRECT_URL" | gcloud secrets versions add DIRECT_URL --data-file=-
printf '%s' "$SECRET_KEY" | gcloud secrets versions add SECRET_KEY --data-file=-
printf '%s' "$GOOGLE_CLIENT_ID" | gcloud secrets versions add GOOGLE_CLIENT_ID --data-file=-
printf '%s' "$GOOGLE_CLIENT_SECRET" | gcloud secrets versions add GOOGLE_CLIENT_SECRET --data-file=-
printf '%s' "$SUPABASE_S3_ACCESS_KEY" | gcloud secrets versions add SUPABASE_S3_ACCESS_KEY --data-file=-
printf '%s' "$SUPABASE_S3_SECRET_KEY" | gcloud secrets versions add SUPABASE_S3_SECRET_KEY --data-file=-
printf '%s' "$EMAIL_HOST_PASSWORD" | gcloud secrets versions add EMAIL_HOST_PASSWORD --data-file=-
```

To confirm the secrets exist:

```bash
gcloud secrets list
```

## Step 5: Review the Runtime Names and URLs

The deployment currently uses these Cloud Run names:

- app service: `wpp-app`
- API service: `wpp-api`
- migration job: `wpp-migrate`

The deployment also keeps these Cloud Run-safe values in the runtime environment:

- `ALLOWED_HOSTS` always includes `.run.app`
- `CSRF_TRUSTED_ORIGINS` always includes `https://*.run.app`

This means future Cloud Run `*.run.app` URLs continue to work without per-release host updates. If you add custom domains, append them instead of replacing the wildcard Cloud Run entries.

## Step 6: Run the Deployment

The fastest path is to use the Poe shortcut:

```bash
poe deploy
```

What `poe deploy` does for you:

- loads `.env` automatically when present
- defaults `GCP_PROJECT_ID` to `worship-prep-portal`
- defaults `GCP_REGION` to `us-west1`
- defaults `RUNTIME_SA` to `wpp-runtime@worship-prep-portal.iam.gserviceaccount.com`
- defaults `SUPABASE_STORAGE_BUCKET` to `wpp-media`
- derives `SUPABASE_S3_ENDPOINT` from `SUPABASE_URL` when needed
- defaults `SUPABASE_S3_REGION` to `us-east-1`
- runs `./deploy/deploy.sh`

If you want to run the deploy script manually instead, load your `.env` first so all required values are available:

```bash
set -a
source .env
set +a
```

Export the deployment variables expected by `deploy/deploy.sh`:

```bash
export GCP_PROJECT_ID=worship-prep-portal
export GCP_REGION=us-west1
export RUNTIME_SA=wpp-runtime@worship-prep-portal.iam.gserviceaccount.com
```

If your `.env` already contains the Supabase storage and SMTP values, no additional
exports are needed—the `source .env` step above makes them available. Otherwise, export
them explicitly:

```bash
export SUPABASE_STORAGE_BUCKET=wpp-media
export SUPABASE_S3_ENDPOINT="https://<PROJECT_REF>.supabase.co/storage/v1/s3"
export SUPABASE_S3_REGION=us-east-1
export EMAIL_HOST=smtp.example.com
export EMAIL_HOST_USER=worship-prep@example.com
export DEFAULT_FROM_EMAIL='Worship Prep <noreply@example.com>'
```

The remaining variables (`AR_REPOSITORY`, `IMAGE_NAME`, `DJANGO_SERVICE`, `BOLT_SERVICE`, `MIGRATE_JOB`) default to the project's standard naming and only need to be exported if you've changed them.

You do not need to export `ALLOWED_HOSTS` or `CSRF_TRUSTED_ORIGINS`. `deploy/deploy.sh` automatically ensures `.run.app` and `https://*.run.app` are present, even if your `.env` file has narrower values.

Run the deployment:

```bash
./deploy/deploy.sh
```

**Important:** `deploy/deploy.sh` defaults `GCP_REGION` to `us-central1`, but this project's infrastructure is in `us-west1`. Always export `GCP_REGION=us-west1` before running the script, or your resources will be created in the wrong region.

What this command does:

1. uploads the source to Cloud Build
2. builds the `prod` and `ingress` Docker targets
3. pushes both images to Artifact Registry
4. deploys the migration job
5. runs migrations
6. deploys the Bolt service with both HTTP startup probes
7. deploys the Django-only app with its HTTP startup probe

## Step 7: Watch the Deployment

List recent builds:

```bash
gcloud builds list --limit=5
```

Describe the latest build:

```bash
gcloud builds describe <BUILD_ID>
```

Read the build log:

```bash
gcloud builds log <BUILD_ID>
```

List the Cloud Run services and jobs:

```bash
gcloud run services list --region=us-west1
gcloud run jobs list --region=us-west1
```

## Step 8: Verify Health Checks

Check the Django service:

```bash
curl -fsSL https://wpp-app-zxdtzfpwua-uw.a.run.app/health/
curl -fsSL https://wpp-app-zxdtzfpwua-uw.a.run.app/ready/
```

Check the API service:

```bash
curl -fsSL https://api.rccgcm.org/api/v1/docs
```

Check the app login page:

```bash
curl -I "https://wpp-app-zxdtzfpwua-uw.a.run.app/accounts/login/?next=/"
```

You should see `200` responses for all of these.

## Step 9: Update the Django Site Record

After the first successful deploy, update the `django.contrib.sites` record so social login and URL generation point at the actual live app host.

Use the stable service URL shown by Cloud Run. First inspect it:

```bash
gcloud run services describe wpp-app --region=us-west1 --format='value(status.url)'
```

Then update the site record:

```bash
set -a
source .env
set +a

uv run python manage.py shell -c "from django.contrib.sites.models import Site; site=Site.objects.get(id=1); site.domain='wpp-app-zxdtzfpwua-uw.a.run.app'; site.name='wpp-app-zxdtzfpwua-uw.a.run.app'; site.save(); print(list(Site.objects.values('id','domain','name')))"
```

Replace `wpp-app-zxdtzfpwua-uw.a.run.app` with your real current service hostname if it differs.

## Step 10: Update Google OAuth Redirect URIs

After a fresh database reset, create the catalog superuser interactively with
`poe manage createsuperuser` before testing Google sign-in. The reset does not copy
legacy accounts, Google identity links, or OAuth tokens. See
[ADR-0010](adr/0010-rebuild-application-in-public.md).

This app uses django-allauth for Google login. The callback path is:

```text
/accounts/google/login/callback/
```

That means your Google OAuth client must authorize at least this redirect URI:

```text
https://wpp-app-zxdtzfpwua-uw.a.run.app/accounts/google/login/callback/
```

If you also use the regional hostname, authorize that too:

```text
https://wpp-app-<PROJECT_NUMBER>.us-west1.run.app/accounts/google/login/callback/
```

At the time of writing, your project's existing OAuth client is managed through the Google Cloud console, not through `gcloud iam oauth-clients`.

Update the redirect URIs in the console:

1. Open Google Cloud Console.
2. Go to Google Auth Platform or APIs & Services.
3. Open Credentials.
4. Open your OAuth 2.0 Client ID.
5. Add the redirect URIs above.
6. Save.

If you later migrate to IAM-managed OAuth clients, the `gcloud` command shape is:

```bash
gcloud iam oauth-clients update <OAUTH_CLIENT_ID> \
  --location=global \
  --project=worship-prep-portal \
  --allowed-redirect-uris="https://wpp-app-zxdtzfpwua-uw.a.run.app/accounts/google/login/callback/,https://wpp-app-<PROJECT_NUMBER>.us-west1.run.app/accounts/google/login/callback/"
```

Important: `--allowed-redirect-uris` replaces the full list. Include every URI you want to keep.

## Step 11: Verify Google Sign-In

Use the preferred service URL:

```text
https://wpp-app-zxdtzfpwua-uw.a.run.app/accounts/login/
```

Open it in an incognito window and test Google sign-in.

Using an incognito window matters because failed social-login attempts can leave behind stale session and state cookies.

## Step 12: Useful Operational Commands

List services:

```bash
gcloud run services list --region=us-west1 --project=worship-prep-portal
```

Describe the app service:

```bash
gcloud run services describe wpp-app --region=us-west1 --project=worship-prep-portal
```

Describe the API service:

```bash
gcloud run services describe wpp-api --region=us-west1 --project=worship-prep-portal
```

Describe the migration job:

```bash
gcloud run jobs describe wpp-migrate --region=us-west1 --project=worship-prep-portal
```

Run migrations again manually:

```bash
gcloud run jobs execute wpp-migrate --region=us-west1 --project=worship-prep-portal --wait
```

Read app logs:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="wpp-app"' \
  --project=worship-prep-portal \
  --limit=50 \
  --format=json
```

Read API logs:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="wpp-api"' \
  --project=worship-prep-portal \
  --limit=50 \
  --format=json
```

### Follow a Catalog Import in Cloud Logging

Cloud Build sets `GCP_PROJECT_ID` on Django, Bolt, and the Nginx ingress. Only
Django and Bolt receive application settings and Secret Manager references.
Nginx propagates bounded
`X-Request-ID` and `X-Cloud-Trace-Context` values; JSON request logs and Catalog
Importer outcome events carry the same full Cloud Logging trace. Valid Cloud Run
trace context is preserved through the API ingress into Bolt. For direct local
runs without a project ID, request IDs still work and no Cloud Logging trace is
attached by the applications.

Find an import's request ID in a `request_finished` event, or start with its
Catalog Import Run ID:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.run_id="RUN_UUID"' \
  --project=worship-prep-portal --limit=50 --format=json
```

Copy `jsonPayload.request_id` to find the request across Nginx and Bolt container
logs, including failures rejected before a Catalog Import Run exists:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.request_id="REQUEST_ID"' \
  --project=worship-prep-portal --limit=100 --format=json
```

Copy the trace identity from `logging.googleapis.com/trace` (shown as `trace`
after Cloud Logging ingests the JSON) to include Cloud Run request logs:

```bash
gcloud logging read 'trace="projects/worship-prep-portal/traces/TRACE_ID"' \
  --project=worship-prep-portal --limit=100 --format=json
```

`catalog_import_received` records the validated package identity even when a
request fails before saving a run. `catalog_import_result` events record the original run ID on success, failure,
and retry, with a safe failure code when processing fails. Request logs include
method, status, and elapsed time; Nginx also includes upstream status and timing
as strings, allowing missing values and multiple upstream attempts. Bolt rejects
some malformed input in Rust before Python dispatch; those requests have the
Nginx ingress event but no Python completion event. The API ingress must preserve
the correlation headers.

Access logs omit query strings, authorization, request bodies, and response
content. Django emits request completion events instead of Gunicorn's plain
access log. Request-specific Nginx error diagnostics are disabled because they
include raw request URLs; Nginx startup diagnostics remain on stderr, and failed
requests retain status and upstream metadata in the JSON access log. Application
exception logs retain exception type without exception messages, traceback source,
or local variables, which can contain credentials or private lyrics. Do not paste
credentials or source content into manual log messages.

## Troubleshooting

### `deploy.sh` fails immediately with "Set SUPABASE_STORAGE_BUCKET" or "Set SUPABASE_S3_ENDPOINT"

Symptom:

- the script exits before uploading anything to Cloud Build

Fix:

- add `SUPABASE_STORAGE_BUCKET` and `SUPABASE_S3_ENDPOINT` to your `.env` file, or export them before running the script
- `SUPABASE_STORAGE_BUCKET` is usually `wpp-media`
- `SUPABASE_S3_ENDPOINT` follows the form `https://<PROJECT_REF>.supabase.co/storage/v1/s3`; the project ref is the subdomain of your `SUPABASE_URL`

### `DisallowedHost`

Symptom:

- Django returns `400`
- logs mention `Invalid HTTP_HOST header`

Fix:

- check whether `.env`, `deploy/deploy.sh`, or a Cloud Build trigger is explicitly setting a narrow `ALLOWED_HOSTS`
- make sure the deployed value still includes `.run.app`
- redeploy the app

### CSRF origin rejected

Symptom:

- Django returns `403 Forbidden`
- the response mentions `Origin checking failed`

Fix:

- check whether `.env`, `deploy/deploy.sh`, or a Cloud Build trigger is explicitly setting a narrow `CSRF_TRUSTED_ORIGINS`
- make sure the deployed value still includes `https://*.run.app`
- redeploy `wpp-app`

### App pages render without CSS or JS

Symptom:

- HTML loads
- `/static/dist/index.css` or `/static/dist/index.js` return `404`

Fix:

- ensure the Docker build generates Reactivated assets before `collectstatic`
- ensure `STATICFILES_DIRS = [BASE_DIR / "static"]`
- ensure production static storage uses `whitenoise.storage.CompressedStaticFilesStorage`
- redeploy `wpp-app`

### Google login shows `Third-Party Login Failure`

Symptom:

- callback page loads but login does not complete

Fix:

- verify the OAuth redirect URI exactly matches the live app callback URL
- verify the `Site` record points to the live app hostname
- retry from an incognito window

### Migration job fails

Symptom:

- Cloud Build fails during `run-migrate-job`

Fix:

- verify `DIRECT_URL` is the direct Supabase Postgres connection on port `5432`
- verify the runtime service account can access Secret Manager
- rerun the job manually after fixing the secret

### Services deploy but cannot connect to the database

Symptom:

- readiness checks fail
- logs mention connection errors

Fix:

- verify `DATABASE_URL` uses the Supabase pooled connection
- verify SSL is enabled in the connection string
- verify the value stored in Secret Manager is current

## Recommended Repeatable Deployment Workflow

For normal future deployments, use this sequence:

```bash
git pull
poe deploy
```

This assumes `.env` exists or that equivalent environment variables are already exported. If `SUPABASE_S3_ENDPOINT` is not set, `poe deploy` derives it from `SUPABASE_URL`. If you prefer not to use the shortcut, you can still follow the manual `./deploy/deploy.sh` flow from Step 6.

Typical build duration is around 5 minutes.

Then verify:

```bash
curl -fsSL https://wpp-app-zxdtzfpwua-uw.a.run.app/health/
curl -fsSL https://wpp-app-zxdtzfpwua-uw.a.run.app/ready/
curl -fsSL https://api.rccgcm.org/api/v1/docs
```

## Final Notes

- Do not commit `.env`.
- Treat Secret Manager as the source of truth for runtime secrets.
- Keep the Django `Site` record aligned with the current live `wpp-app` hostname.
- Keep the Google OAuth redirect URI aligned with the current live `wpp-app` hostname.
- Use the preferred stable app URL consistently when testing login flows.
