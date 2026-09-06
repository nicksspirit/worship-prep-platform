import hashlib
import io
import json
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.catalog.importer import ImportRejected, import_package, recover_import_run
from apps.catalog.models import (
    CatalogEntry,
    CatalogImportEvent,
    CatalogImportRun,
    CatalogSongRights,
    CatalogState,
    ImportStatus,
    ImportTrigger,
    LyricsRightsChange,
    RightsBasis,
    RightsStatus,
)
from apps.catalog.rights import change_lyrics_rights


class CatalogAdministrationTests(TransactionTestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            email="superuser@example.com",
            password="pass1234",
            first_name="Super",
            last_name="User",
        )
        self.catalog_admin = get_user_model().objects.create_user(
            email="catalog.admin@example.com",
            password="pass1234",
            first_name="Catalog",
            last_name="Admin",
            is_staff=True,
        )

    @staticmethod
    def build_package(*, run_id=None, valid_checksum=True):
        fixture_dir = (
            Path(settings.BASE_DIR) / "contracts/catalog-import/v1/fixtures/valid"
        )
        manifest = json.loads((fixture_dir / "manifest.json").read_text())
        records = (fixture_dir / "songs.ndjson").read_bytes()
        digest = f"sha256:{hashlib.sha256(records).hexdigest()}"
        manifest["run_id"] = str(run_id or uuid.uuid4())
        manifest["records"].update(
            bytes=len(records),
            sha256=digest if valid_checksum else "sha256:" + "0" * 64,
            fingerprint=digest if valid_checksum else "sha256:" + "0" * 64,
        )
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("songs.ndjson", records)
        return package.getvalue(), manifest

    def test_rights_change_requires_superuser_policy_evidence_and_is_audited(self):
        first_package, _manifest = self.build_package()
        first = import_package(first_package).run.snapshot
        rights = CatalogSongRights.objects.get(song_uid="fixture-song-uid")
        self.assertEqual(rights.status, RightsStatus.UNKNOWN)

        with self.assertRaises(PermissionDenied):
            change_lyrics_rights(
                rights,
                status=RightsStatus.RESTRICTED,
                basis=RightsBasis.OWNER_REQUEST,
                evidence_reference="Owner email 2026-08-01",
                explanation="Owner requested that web lyrics be withheld.",
                user=self.catalog_admin,
            )
        with self.assertRaises(ValidationError):
            change_lyrics_rights(
                rights,
                status=RightsStatus.APPROVED,
                basis=RightsBasis.OWNER_REQUEST,
                evidence_reference="Owner email 2026-08-01",
                explanation="Wrong basis for approval.",
                user=self.superuser,
            )

        decision = change_lyrics_rights(
            rights,
            status=RightsStatus.RESTRICTED,
            basis=RightsBasis.OWNER_REQUEST,
            evidence_reference="Owner email 2026-08-01",
            explanation="Owner requested that web lyrics be withheld.",
            user=self.superuser,
        )

        rights.refresh_from_db()
        self.assertEqual(rights.status, RightsStatus.RESTRICTED)
        self.assertEqual(decision.previous_status, RightsStatus.UNKNOWN)
        self.assertEqual(decision.decided_by, self.superuser)
        self.assertEqual(LyricsRightsChange.objects.count(), 1)
        self.assertEqual(
            CatalogEntry.objects.get(snapshot=first).rights_status,
            RightsStatus.RESTRICTED,
        )

        second_package, _manifest = self.build_package()
        second = import_package(second_package).run.snapshot
        self.assertEqual(
            CatalogEntry.objects.get(snapshot=second).rights_status,
            RightsStatus.RESTRICTED,
        )

    def test_import_history_separates_delivery_validation_staging_and_promotion(self):
        package, _manifest = self.build_package()
        run = import_package(package).run

        stages = list(run.events.values_list("event", "outcome"))
        self.assertIn(("package_created", "completed"), stages)
        self.assertIn(("package_received", "completed"), stages)
        self.assertIn(("validation", "completed"), stages)
        self.assertIn(("staging", "started"), stages)
        self.assertIn(("staging", "completed"), stages)
        self.assertIn(("promotion", "completed"), stages)

    def test_catalog_admin_can_view_but_only_superuser_can_change_rights(self):
        package, _manifest = self.build_package()
        import_package(package)
        rights = CatalogSongRights.objects.get()
        url = reverse("admin:catalog_catalogsongrights_change", args=[rights.pk])

        self.client.force_login(self.catalog_admin)
        view_response = self.client.get(url)
        self.assertEqual(view_response.status_code, 200)
        post_response = self.client.post(
            url,
            {
                "status": RightsStatus.RESTRICTED,
                "basis": RightsBasis.OWNER_REQUEST,
                "evidence_reference": "Owner email",
                "explanation": "Withhold lyrics.",
            },
        )
        self.assertEqual(post_response.status_code, 403)

        self.client.force_login(self.superuser)
        response = self.client.post(
            url,
            {
                "status": RightsStatus.RESTRICTED,
                "basis": RightsBasis.OWNER_REQUEST,
                "evidence_reference": "Owner email",
                "explanation": "Withhold lyrics.",
                "_save": "Save",
                "changes-TOTAL_FORMS": "0",
                "changes-INITIAL_FORMS": "0",
                "changes-MIN_NUM_FORMS": "0",
                "changes-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(response.status_code, 302)
        rights.refresh_from_db()
        self.assertEqual(rights.status, RightsStatus.RESTRICTED)

    def test_failed_retained_package_can_be_recovered_without_exporter_rerun(self):
        package, _manifest = self.build_package()
        with patch(
            "apps.catalog.importer._stage_and_promote",
            side_effect=RuntimeError("temporary database failure"),
        ):
            with self.assertRaises(RuntimeError):
                import_package(package)
        run = CatalogState.objects.filter(pk=1).first()
        self.assertTrue(run is None or run.active_snapshot is None)
        self.assertFalse(CatalogSongRights.objects.exists())

        import_run = CatalogImportRun.objects.get()
        self.assertEqual(import_run.status, ImportStatus.FAILED)
        recovered = recover_import_run(import_run, user=self.superuser)

        self.assertEqual(recovered.status, ImportStatus.COMPLETED)
        self.assertEqual(CatalogState.objects.get().active_snapshot.import_run, recovered)
        self.assertTrue(
            recovered.events.filter(event="recovery", outcome="requested").exists()
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="Worship Prep <noreply@example.com>",
    )
    def test_scheduled_failure_preserves_catalog_and_alerts_superusers(self):
        valid, _manifest = self.build_package()
        import_package(valid)
        active = CatalogState.objects.get().active_snapshot
        invalid, manifest = self.build_package(valid_checksum=False)

        with self.assertRaises(ImportRejected):
            import_package(invalid, trigger=ImportTrigger.SCHEDULED)

        self.assertEqual(CatalogState.objects.get().active_snapshot, active)
        failed = active.import_run.__class__.objects.get(pk=manifest["run_id"])
        self.assertEqual(failed.trigger, ImportTrigger.SCHEDULED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(failed.pk), mail.outbox[0].body)
        self.assertIn("/admin/catalog/catalogimportrun/", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].bcc, [self.superuser.email])

    def test_exporter_events_are_replayed_idempotently(self):
        package, manifest = self.build_package()
        event = {
            "run_id": manifest["run_id"],
            "type": "started",
            "outcome": "completed",
            "occurred_at": timezone.now().isoformat(),
            "details": {"scheduled": True},
        }
        events = (json.dumps(event) + "\n").encode()

        result = import_package(
            package,
            exporter_events=events,
            trigger=ImportTrigger.SCHEDULED,
        )
        import_package(
            package,
            exporter_events=events,
            trigger=ImportTrigger.SCHEDULED,
        )

        self.assertEqual(
            CatalogImportEvent.objects.filter(
                import_run=result.run,
                source=CatalogImportEvent.Source.EXPORTER,
                event="started",
            ).count(),
            1,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_scheduled_retry_reprocesses_the_same_run_and_package_once(self):
        package, manifest = self.build_package()
        with patch(
            "apps.catalog.importer._stage_and_promote",
            side_effect=RuntimeError("temporary database failure"),
        ):
            with self.assertRaises(RuntimeError):
                import_package(package, trigger=ImportTrigger.SCHEDULED)

        result = import_package(package, trigger=ImportTrigger.SCHEDULED)

        self.assertFalse(result.created)
        self.assertEqual(str(result.run.pk), manifest["run_id"])
        self.assertEqual(result.run.status, ImportStatus.COMPLETED)
        self.assertEqual(
            CatalogState.objects.get().active_snapshot.import_run,
            result.run,
        )
        self.assertEqual(
            result.run.events.filter(event="retry", outcome="requested").count(),
            1,
        )

    def test_catalog_admin_cannot_open_api_key_administration(self):
        self.client.force_login(self.catalog_admin)
        response = self.client.get(reverse("admin:api_keys_integrationapikey_add"))
        self.assertEqual(response.status_code, 403)

    def test_rights_provenance_tables_are_not_exposed_to_supabase_api_roles(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT relname, relrowsecurity
                FROM pg_catalog.pg_class
                WHERE relname = ANY(%s)
                """,
                [["catalog_catalogsongrights", "catalog_lyricsrightschange"]],
            )
            policies = dict(cursor.fetchall())

        self.assertEqual(
            policies,
            {
                "catalog_catalogsongrights": True,
                "catalog_lyricsrightschange": True,
            },
        )
