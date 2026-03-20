#!/usr/bin/env bash
# Creates a private storage bucket in Supabase for Django media (Song.lyrics_file, etc.).
#
# Prerequisites: Supabase CLI logged in (`supabase login`) and project linked, or set
# SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF.
#
# Usage:
#   export SUPABASE_BUCKET_NAME=worship-prep-media
#   ./deploy/setup-supabase-storage.sh
#
set -euo pipefail

BUCKET_NAME="${SUPABASE_BUCKET_NAME:-worship-prep-media}"

if ! command -v supabase >/dev/null 2>&1; then
  echo "Install the Supabase CLI: https://supabase.com/docs/guides/cli" >&2
  exit 1
fi

echo "Creating storage bucket '${BUCKET_NAME}' (idempotent if it already exists)."
supabase storage create "${BUCKET_NAME}" --public false || true

echo "Done. Set SUPABASE_STORAGE_BUCKET=${BUCKET_NAME} and configure S3-compatible credentials in your env / Secret Manager."
