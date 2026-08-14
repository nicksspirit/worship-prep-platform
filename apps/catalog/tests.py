import hashlib
import io
import json
import uuid
import zipfile
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

from asgiref.sync import async_to_sync
from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django_bolt import UploadFile

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import issue_api_key
from apps.catalog.api import api as catalog_api
from apps.catalog.api import catalog_import
from apps.catalog.importer import rollback_to_snapshot
from apps.catalog.models import (
    CatalogEntry,
    CatalogImportRun,
    CatalogSnapshot,
    CatalogState,
    ImportStatus,
    RightsStatus,
)


class GreenfieldRuntimeTests(TestCase):
    def test_health_and_readiness_boot(self):
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})
        self.assertEqual(self.client.get(reverse("ready")).status_code, 200)

    def test_static_assets_remain_discoverable(self):
        self.assertIsNotNone(finders.find("rccgcm_logo.png"))
        self.assertIsNotNone(finders.find("install-catalog-exporter.ps1"))

    def test_catalog_exporter_install_bootstrap_is_pipeable(self):
        response = self.client.get("/install")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("#Requires -Version 7.4", response.content.decode())
        self.assertIn(
            "http://testserver/static/install-catalog-exporter.ps1",
            response.content.decode(),
        )

    def test_greenfield_modules_are_installed(self):
        self.assertEqual(apps.get_app_config("accounts").name, "apps.accounts")
        self.assertEqual(apps.get_app_config("api_keys").name, "apps.api_keys")
        self.assertEqual(apps.get_app_config("catalog").name, "apps.catalog")

    def test_legacy_modules_and_routes_are_absent(self):
        self.assertIsNone(find_spec("apps.schedules"))
        self.assertIsNone(find_spec("apps.songs"))
        for path in (
            "/schedule/",
            "/api/v1/schedules",
            "/api/v1/schedules/intake",
            "/api/v1/songs/intake",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_database_uses_only_fresh_product_migrations(self):
        loader = MigrationLoader(connection)
        migrated_apps = {app_label for app_label, _name in loader.disk_migrations}

        self.assertTrue({"accounts", "api_keys", "catalog"} <= migrated_apps)
        self.assertTrue({"users", "schedules", "songs"}.isdisjoint(migrated_apps))

    def test_models_have_no_unrecorded_migration_changes(self):
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)


class CatalogImporterTests(TransactionTestCase):
    def setUp(self):
        _key, self.plaintext_key = issue_api_key(
            name="Exporter", scopes=[APIKeyScope.CATALOG_IMPORT]
        )

    def build_package(self, *, run_id=None, transform_record=None, valid_checksum=True):
        fixture_dir = (
            Path(settings.BASE_DIR) / "contracts/catalog-import/v1/fixtures/valid"
        )
        manifest = json.loads((fixture_dir / "manifest.json").read_text())
        record = json.loads((fixture_dir / "songs.ndjson").read_text())
        manifest["run_id"] = str(run_id or uuid.uuid4())
        if transform_record:
            transform_record(record)
        records = (json.dumps(record, separators=(",", ":")) + "\n").encode()
        digest = f"sha256:{hashlib.sha256(records).hexdigest()}"
        manifest["records"].update(
            bytes=len(records),
            sha256=digest if valid_checksum else "sha256:" + "0" * 64,
            fingerprint=digest if valid_checksum else "sha256:" + "0" * 64,
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("songs.ndjson", records)
        return buffer.getvalue(), manifest["run_id"]

    def post_package(self, package, *, key=None):
        upload = UploadFile(
            filename="catalog.zip",
            content_type="application/zip",
            size=len(package),
            file_data=package,
        )
        response = async_to_sync(catalog_import)(
            upload,
            f"Bearer {key or self.plaintext_key}",
        )
        if isinstance(response, tuple):
            return SimpleNamespace(status_code=response[0])
        return response

    def test_json_import_is_registered_only_with_bolt(self):
        routes = {
            (method, path)
            for method, path, _handler_id, _handler in catalog_api._routes
        }
        self.assertIn(("POST", "/api/v1/catalog/imports"), routes)
        self.assertEqual(self.client.post("/api/v1/catalog/imports").status_code, 404)

    def test_requires_import_scoped_bearer_key(self):
        package, _run_id = self.build_package()
        upload = UploadFile(
            filename="catalog.zip", size=len(package), file_data=package
        )
        response = async_to_sync(catalog_import)(upload, "")
        self.assertEqual(response[0], 401)

        _search_key, plaintext = issue_api_key(
            name="Search", scopes=[APIKeyScope.CATALOG_SEARCH]
        )
        self.assertEqual(self.post_package(package, key=plaintext).status_code, 403)

    def test_valid_package_creates_private_completed_snapshot(self):
        package, run_id = self.build_package()
        response = self.post_package(package)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.to_bytes())["status"], "completed")

        run = CatalogImportRun.objects.get(pk=run_id)
        active_snapshot = CatalogState.objects.get().active_snapshot
        entry = CatalogEntry.objects.get(snapshot=active_snapshot)
        self.assertEqual(run.status, ImportStatus.COMPLETED)
        self.assertTrue(run.package_file.name.startswith("packages/"))
        self.assertTrue(run.report_file.name.startswith("reports/"))
        self.assertEqual(entry.rights_status, RightsStatus.UNKNOWN)
        self.assertEqual(entry.title, "Amazing Grace")
        self.assertIsNotNone(entry.title_search)
        self.assertIsNotNone(entry.lyrics_search)

    def test_same_run_and_package_is_idempotent_but_conflict_is_rejected(self):
        run_id = uuid.uuid4()
        package, _ = self.build_package(run_id=run_id)
        self.assertEqual(self.post_package(package).status_code, 201)
        self.assertEqual(self.post_package(package).status_code, 200)
        self.assertEqual(CatalogSnapshot.objects.count(), 1)

        conflicting, _ = self.build_package(
            run_id=run_id,
            transform_record=lambda record: record["metadata"].update(title="Conflict"),
        )
        self.assertEqual(self.post_package(conflicting).status_code, 409)
        self.assertEqual(CatalogSnapshot.objects.count(), 1)

    def test_invalid_package_leaves_active_snapshot_unchanged(self):
        valid, _ = self.build_package()
        self.assertEqual(self.post_package(valid).status_code, 201)
        active = CatalogState.objects.get().active_snapshot

        invalid, run_id = self.build_package(valid_checksum=False)
        response = self.post_package(invalid)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(CatalogState.objects.get().active_snapshot, active)
        failed = CatalogImportRun.objects.get(pk=run_id)
        self.assertEqual(failed.status, ImportStatus.FAILED)
        self.assertEqual(failed.failure_code, "records_integrity_failed")

    def test_unchanged_song_keeps_freshness_and_rollback_moves_only_pointer(self):
        first, _ = self.build_package()
        self.post_package(first)
        first_snapshot = CatalogState.objects.get().active_snapshot
        original_freshness = first_snapshot.entries.get().content_changed_at

        second, _ = self.build_package()
        self.post_package(second)
        second_snapshot = CatalogState.objects.get().active_snapshot
        second_freshness = second_snapshot.entries.get().content_changed_at
        self.assertEqual(second_freshness, original_freshness)

        activation = rollback_to_snapshot(first_snapshot)
        self.assertEqual(CatalogState.objects.get().active_snapshot, first_snapshot)
        self.assertEqual(activation.previous_snapshot, second_snapshot)
        self.assertEqual(CatalogSnapshot.objects.count(), 2)

    def test_changed_song_gets_new_freshness_and_retention_keeps_eight_snapshots(self):
        first, _ = self.build_package()
        self.post_package(first)
        first_entry = CatalogState.objects.get().active_snapshot.entries.get()
        original_freshness = first_entry.content_changed_at

        def change_song(record):
            record["metadata"]["title"] = "Amazing Grace (Revised)"
            record["semantic_fingerprint"]["value"] = "sha256:" + "a" * 64

        changed, _ = self.build_package(transform_record=change_song)
        self.post_package(changed)
        changed_entry = CatalogState.objects.get().active_snapshot.entries.get()
        changed_freshness = changed_entry.content_changed_at
        self.assertGreater(changed_freshness, original_freshness)

        for _ in range(7):
            package, _run_id = self.build_package(transform_record=change_song)
            self.assertEqual(self.post_package(package).status_code, 201)
        self.assertEqual(CatalogSnapshot.objects.count(), 8)
