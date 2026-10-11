"""Follow actual Catalog Import requests and retries through their JSON log output."""

import io
import json
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.test import TransactionTestCase
from django_bolt.testing import TestClient

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import IssueApiKey, issue_api_key
from apps.catalog.api import api
from apps.common.tests.test_request_logging import capture_logs


class CatalogImportLogTests(TransactionTestCase):
    def package(self, *, valid=True):
        fixture = Path(settings.BASE_DIR) / "contracts/catalog-import/v1/fixtures/valid"
        manifest = json.loads((fixture / "manifest.json").read_text())
        manifest["run_id"] = str(uuid.uuid4())
        if not valid:
            manifest["records"]["sha256"] = "sha256:" + "0" * 64
        buffer = io.BytesIO()
        records = (fixture / "songs.ndjson").read_bytes()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("songs.ndjson", records)
        return (
            buffer.getvalue(),
            manifest["run_id"],
            json.loads(records)["cleaned_lyrics"],
        )

    def test_retry_logs_the_original_run_identity_with_each_request(self):
        secret = issue_api_key(
            IssueApiKey("Exporter", [APIKeyScope.CATALOG_IMPORT])
        ).plaintext_key
        package, run_id, lyrics = self.package()
        with (
            self.settings(GCP_PROJECT_ID="wpp-test-project"),
            capture_logs() as logs,
            TestClient(api, read_django_settings=False) as client,
        ):
            responses = [
                client.post(
                    "/api/v1/catalog/imports",
                    files={"package": ("catalog.zip", package, "application/zip")},
                    headers={
                        "authorization": f"Bearer {secret}",
                        "x-request-id": request_id,
                        "x-cloud-trace-context": "0123456789abcdef0123456789abcdef/42;o=1",
                    },
                )
                for request_id in ("first-123", "retry-123")
            ]
        self.assertEqual([response.status_code for response in responses], [201, 200])
        self.assertEqual(
            [response.json()["run_id"] for response in responses], [run_id, run_id]
        )
        events = [json.loads(line) for line in logs.getvalue().splitlines()]
        outcomes = [
            event for event in events if event["event"] == "catalog_import_result"
        ]
        self.assertEqual(
            [(event["run_id"], event["request_id"]) for event in outcomes],
            [(run_id, "first-123"), (run_id, "retry-123")],
        )
        self.assertTrue(
            all(
                event["logging.googleapis.com/trace"]
                == "projects/wpp-test-project/traces/0123456789abcdef0123456789abcdef"
                for event in outcomes
            )
        )
        self.assertNotIn(secret, logs.getvalue())
        self.assertNotIn(lyrics, logs.getvalue())

    def test_failed_import_logs_its_run_and_safe_failure_code(self):
        secret = issue_api_key(
            IssueApiKey("Exporter", [APIKeyScope.CATALOG_IMPORT])
        ).plaintext_key
        package, run_id, lyrics = self.package(valid=False)
        with (
            capture_logs() as logs,
            TestClient(api, read_django_settings=False) as client,
        ):
            response = client.post(
                "/api/v1/catalog/imports",
                files={"package": ("catalog.zip", package, "application/zip")},
                headers={
                    "authorization": f"Bearer {secret}",
                    "x-request-id": "failed-123",
                },
            )
        self.assertEqual(response.status_code, 422)
        events = [json.loads(line) for line in logs.getvalue().splitlines()]
        outcome = next(
            event for event in events if event["event"] == "catalog_import_result"
        )
        self.assertEqual(
            (
                outcome["run_id"],
                outcome["request_id"],
                outcome["status"],
                outcome["failure_code"],
            ),
            (run_id, "failed-123", "failed", "records_integrity_failed"),
        )
        self.assertNotIn(secret, logs.getvalue())
        self.assertNotIn(lyrics, logs.getvalue())

    def test_rejected_credentials_log_request_without_inventing_a_run(self):
        package, _, lyrics = self.package()
        with (
            capture_logs() as logs,
            TestClient(api, read_django_settings=False) as client,
        ):
            response = client.post(
                "/api/v1/catalog/imports",
                files={"package": ("catalog.zip", package, "application/zip")},
                headers={
                    "authorization": "Bearer private-key",
                    "x-request-id": "rejected-123",
                },
            )
        self.assertEqual(response.status_code, 401)
        events = [json.loads(line) for line in logs.getvalue().splitlines()]
        outcome = next(event for event in events if event["event"] == "request_finished")
        self.assertEqual(
            (outcome["request_id"], outcome["status"]), ("rejected-123", 401)
        )
        self.assertTrue(all("run_id" not in event for event in events))
        self.assertNotIn("private-key", logs.getvalue())
        self.assertNotIn(lyrics, logs.getvalue())
