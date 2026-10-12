"""Real exporter -> API TLS/H2 -> Nginx h2c ingress -> Bolt -> importer.

Run in Dockerfile.proxy-test with WPP_HTTP2_TEST_DATABASE_URL pointing at a
disposable PostgreSQL database. This script migrates that database.
"""

import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
import zipfile

from proxy_fixture import TLSProxy, free_port

SOURCE = Path(__file__).resolve().parents[2]
MIB = 1024 * 1024


class LargeImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ["WPP_HTTP2_TEST_DATABASE_URL"]
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        (cls.root / "http2_settings.py").write_text(
            'from backend.settings import *\n'
            f'STORAGES["catalog_imports"] = {{"BACKEND": '
            f'"django.core.files.storage.FileSystemStorage", '
            f'"OPTIONS": {{"location": "{cls.root}/imports"}}}}\n'
            'LOGGING["handlers"]["console"]["formatter"] = "json"\n'
        )
        os.environ.update(
            DJANGO_ENV="test", DATABASE_URL=database_url,
            DJANGO_SETTINGS_MODULE="http2_settings",
            PYTHONUNBUFFERED="1", GCP_PROJECT_ID="wpp-test-project",
            PYTHONPATH=f"{cls.root}:{SOURCE}",
        )
        sys.path.insert(0, str(cls.root))
        sys.path.insert(0, str(SOURCE))
        import django
        django.setup()
        from django.core.management import call_command
        from apps.api_keys.models import APIKeyScope
        from apps.api_keys.services import IssueApiKey, issue_api_key
        call_command("migrate", verbosity=0, interactive=False)
        cls.key = issue_api_key(IssueApiKey(
            name="HTTP2 fixture", scopes=[APIKeyScope.CATALOG_IMPORT],
        )).plaintext_key
        cls.search_key = issue_api_key(IssueApiKey(
            name="HTTP2 search fixture", scopes=[APIKeyScope.CATALOG_SEARCH],
        )).plaintext_key
        certificate = cls.root / "certificate.pem"
        key = cls.root / "private-key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(certificate), "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
        ], check=True, capture_output=True)
        cls.certificate = certificate
        cls.bolt_port = free_port()
        # Nginx reopens /dev/stdout; append prevents independent writers overwriting.
        cls.logs = (cls.root / "processes.log").open("a+")
        cls.addClassCleanup(cls.logs.close)
        cls.processes = []
        cls.addClassCleanup(cls.stop_processes)

        bolt_root = cls.root / "bolt"
        (bolt_root / "deploy").mkdir(parents=True)
        shutil.copy(SOURCE / "deploy/start-bolt.sh", bolt_root / "deploy")
        backend_port = free_port()
        shutil.copy(SOURCE / "manage.py", bolt_root)
        cls.processes.append(subprocess.Popen(
            ["bash", str(bolt_root / "deploy/start-bolt.sh")],
            env={**os.environ, "BOLT_PORT": str(backend_port)},
            stdout=cls.logs, stderr=cls.logs,
        ))
        cls.wait_for(backend_port, "/api/v1/docs")
        logging = (SOURCE / "deploy/nginx-logging.conf.template").read_text()
        (cls.root / "logging.conf").write_text(
            logging.replace("${GCP_PROJECT_ID}", "wpp-test-project")
        )
        config = (SOURCE / "deploy/nginx-bolt.conf.template").read_text()
        config = (config.replace("/tmp/wpp-nginx", str(cls.root / "nginx"))
                  .replace(str(cls.root / "nginx-logging.conf"), str(cls.root / "logging.conf"))
                  .replace("${PORT}", str(cls.bolt_port))
                  .replace("127.0.0.1:8000", f"127.0.0.1:{backend_port}"))
        config_path = cls.root / "nginx.conf"
        config_path.write_text(config)
        cls.processes.append(subprocess.Popen(
            ["nginx", "-e", "stderr", "-c", str(config_path), "-g", "daemon off;"],
            stdout=cls.logs, stderr=cls.logs,
        ))
        cls.wait_for(cls.bolt_port, "/api/v1/docs")
        cls.bolt_edge = TLSProxy(cls.root, cls.bolt_port, certificate, key,
                                 http2_upstream=True)
        cls.addClassCleanup(cls.bolt_edge.close)

        cls.endpoint = f"https://localhost:{cls.bolt_edge.port}"

    @classmethod
    def wait_for(cls, port, path):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            try:
                connection.request("GET", path)
                response = connection.getresponse()
                response.read()
                if response.status == 200:
                    return
            except OSError:
                pass
            finally:
                connection.close()
            if any(process.poll() is not None for process in cls.processes):
                break
            time.sleep(0.5)
        cls.logs.flush()
        raise AssertionError("\n".join(
            (cls.root / "processes.log").read_text().splitlines()[-30:]
        ))

    @classmethod
    def stop_processes(cls):
        for process in reversed(cls.processes):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)

    def build_package(self, records_mib=1, *, title="HTTP2 Catalog", checksum=True):
        fixture = SOURCE / "contracts/catalog-import/v1/fixtures/valid"
        manifest = json.loads((fixture / "manifest.json").read_text())
        record = json.loads((fixture / "songs.ndjson").read_text())
        run_id = str(uuid.uuid4())
        manifest["run_id"] = run_id
        record["metadata"]["title"] = title
        record["raw_lyrics"]["content"] = "{\\rtf1 " + "x" * (MIB // 2) + "}"
        records = self.root / f"{run_id}.ndjson"
        digest = hashlib.sha256()
        count = 0
        with records.open("wb") as stream:
            while stream.tell() < records_mib * MIB - MIB:
                song = copy.deepcopy(record)
                song["source"].update(song_uid=f"{run_id}-{count}",
                                       song_item_uid=f"item-{run_id}-{count}")
                encoded = (json.dumps(song) + "\n").encode()
                stream.write(encoded)
                digest.update(encoded)
                count += 1
            # Stay within the 120 MiB expanded-record limit, including JSON framing.
            record["source"].update(song_uid=f"{run_id}-{count}",
                                      song_item_uid=f"item-{run_id}-{count}")
            record["raw_lyrics"]["content"] = "{\\rtf1 " + "x" * (MIB // 4) + "}"
            encoded = (json.dumps(record) + "\n").encode()
            stream.write(encoded)
            digest.update(encoded)
            count += 1
        manifest["counts"]["songs"] = count
        sha = "sha256:" + (digest.hexdigest() if checksum else "0" * 64)
        manifest["records"].update(bytes=records.stat().st_size,
                                    sha256=sha, fingerprint=sha)
        manifest_bytes = json.dumps(manifest).encode()
        # Valid JSON whitespace gives a representative near expanded-manifest limit.
        manifest_bytes += b" " * (MIB - len(manifest_bytes))
        package = self.root / f"{run_id}.zip"
        with zipfile.ZipFile(package, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", manifest_bytes)
            archive.write(records, "songs.ndjson")
        events = self.root / f"{run_id}-events.ndjson"
        event = {"run_id": run_id, "type": "package_created", "outcome": "succeeded",
                 "occurred_at": "2026-10-11T12:00:00Z", "details": {"error": ""}}
        empty = (json.dumps(event) + "\n").encode()
        event["details"]["error"] = "x" * (MIB - len(empty))
        events.write_text(json.dumps(event) + "\n")
        return package, events

    def deliver(self, package, events="", key=None, endpoint=None):
        return subprocess.run([
            "/tmp/deliver-fixture", endpoint or self.endpoint, str(self.certificate),
            str(package), str(events), key or self.key,
        ], capture_output=True, text=True, timeout=600)

    def read_catalog(self):
        from apps.catalog.services import SearchCatalog, search_catalog
        page = search_catalog(SearchCatalog(limit=100))
        return page.snapshot_completed_at, [item.song_uid for item in page.items]

    def test_direct_bolt_ingress_preserves_safe_request_and_trace_identity(self):
        trace_id = "0123456789abcdef0123456789abcdef"
        result = subprocess.run([
            "curl", "--http2", "--cacert", str(self.certificate), "--silent",
            "--output", "/dev/null", "--write-out", "%{http_code}",
            "--header", "X-Request-ID: direct-bolt-123",
            "--header", f"X-Cloud-Trace-Context: {trace_id}/42;o=1",
            "--header", "Authorization: Bearer private-correlation-key",
            f"https://localhost:{self.bolt_edge.port}"
            "/api/v1/catalog/search?key=private-correlation-query",
        ], capture_output=True, text=True, timeout=30)

        self.assertEqual(result.stdout, "401", result.stderr)
        time.sleep(0.1)
        output = (self.root / "processes.log").read_text()
        events = [json.loads(line) for line in output.splitlines()
                  if line.startswith("{")]
        correlated = [event for event in events
                      if event.get("request_id") == "direct-bolt-123"]
        self.assertEqual(len(correlated), 2, correlated)
        for event in correlated:
            self.assertEqual(event["status"], 401)
            self.assertEqual(event["path"], "/api/v1/catalog/search")
            self.assertEqual(event["logging.googleapis.com/trace"],
                             f"projects/wpp-test-project/traces/{trace_id}")
        self.assertNotIn("private-correlation-query", output)
        self.assertNotIn("private-correlation-key", output)

    def test_successful_import_logs_share_proxy_request_and_cloud_trace(self):
        package, events = self.build_package()
        trace_id = "0123456789abcdef0123456789abcdef"
        offset = (self.root / "processes.log").stat().st_size
        result = subprocess.run([
            "curl", "--http2", "--cacert", str(self.certificate), "--silent",
            "--output", "/dev/null", "--write-out", "%{http_code}",
            "--header", "X-Request-ID: import-trace-123",
            "--header", f"X-Cloud-Trace-Context: {trace_id}/42;o=1",
            "--header", f"Authorization: Bearer {self.key}",
            "--form", f"package=@{package};type=application/zip",
            "--form", f"events=@{events};type=application/x-ndjson",
            f"{self.endpoint}/api/v1/catalog/imports?key=private-import-query",
        ], capture_output=True, text=True, timeout=60)

        self.assertEqual(result.stdout, "201", result.stderr)
        time.sleep(0.1)
        output = (self.root / "processes.log").read_bytes()[offset:].decode()
        logs = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
        correlated = [event for event in logs if event.get("request_id") == "import-trace-123"]
        self.assertEqual(sorted(event["event"] for event in correlated),
                         ["catalog_import_received", "catalog_import_result",
                          "request_finished", "request_finished"])
        for event in correlated:
            self.assertEqual(event["logging.googleapis.com/trace"],
                             f"projects/wpp-test-project/traces/{trace_id}")
        self.assertNotIn(self.key, output)
        self.assertNotIn("private-import-query", output)

    def test_direct_bolt_ingress_generates_and_forwards_request_identity(self):
        offset = (self.root / "processes.log").stat().st_size
        result = subprocess.run([
            "curl", "--http2", "--cacert", str(self.certificate), "--silent",
            "--output", "/dev/null", "--write-out", "%{http_code}",
            "--header", "Authorization: Bearer private-correlation-key",
            f"https://localhost:{self.bolt_edge.port}/api/v1/catalog/search",
        ], capture_output=True, text=True, timeout=30)

        self.assertEqual(result.stdout, "401", result.stderr)
        time.sleep(0.1)
        output = (self.root / "processes.log").read_bytes()[offset:].decode()
        events = [json.loads(line) for line in output.splitlines()
                  if line.startswith("{")]
        requests = [event for event in events
                    if event.get("event") == "request_finished"
                    and event.get("path") == "/api/v1/catalog/search"
                    and event.get("status") == 401]
        self.assertEqual(len(requests), 2, output)
        identities = {event["request_id"] for event in requests}
        self.assertEqual(len(identities), 1)
        self.assertRegex(identities.pop(), r"^[0-9a-f]{32}$")

    def test_exporter_imports_small_large_and_near_limit_packages(self):
        for mib in (1, 33, 120):
            with self.subTest(records_mib=mib):
                package, events = self.build_package(mib)
                result = self.deliver(package, events)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(self.read_catalog()[1])
                print(f"Imported valid package {package.stat().st_size} bytes with "
                      f"{events.stat().st_size} event bytes", flush=True)
        self.assertEqual(
            set(self.bolt_edge.access_log.read_text().splitlines()), {"HTTP/2.0"}
        )
        pid = self.processes[0].pid
        children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        for child in [str(pid), *children]:
            status = Path(f"/proc/{child}/status").read_text()
            print("Bolt process peak memory: " + next(
                line for line in status.splitlines() if line.startswith("VmHWM:")),
                flush=True)

    def test_failed_uploads_preserve_the_active_song_catalog(self):
        package, events = self.build_package(title="Preserved Catalog")
        self.assertEqual(self.deliver(package).returncode, 0)
        before = self.read_catalog()
        bad_checksum, _ = self.build_package(checksum=False)
        invalid_zip = self.root / "invalid.zip"
        invalid_zip.write_bytes(b"invalid")
        oversized = self.root / "oversized.zip"
        with oversized.open("wb") as stream:
            stream.truncate(128 * MIB + 1)
        too_many_events = self.root / "large-events.ndjson"
        with too_many_events.open("wb") as stream:
            stream.truncate(MIB + 1)
        envelope = self.root / "large-envelope.zip"
        with envelope.open("wb") as stream:
            stream.truncate(130 * MIB + 1)
        for label, candidate, timeline, credential, status in (
            ("unauthorized", package, events, "invalid-key", "401"),
            ("wrong scope", package, events, self.search_key, "403"),
            ("invalid ZIP", invalid_zip, "", self.key, "422"),
            ("invalid checksum", bad_checksum, "", self.key, "422"),
            ("oversized package", oversized, "", self.key, "422"),
            ("oversized events", package, too_many_events, self.key, "422"),
        ):
            with self.subTest(failure=label):
                result = self.deliver(candidate, timeline, credential)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(status, result.stderr)
                self.assertEqual(self.read_catalog(), before)
        # Known total size lets Nginx reject the envelope before reading a part.
        # The streaming Go client instead receives Bolt's earlier part-size error.
        result = subprocess.run([
            "curl", "--http2", "--cacert", str(self.certificate),
            "--silent", "--output", "/dev/null", "--write-out", "%{http_code}",
            "--header", "Content-Type: multipart/form-data; boundary=fixture",
            "--data-binary", f"@{envelope}",
            f"{self.endpoint}/api/v1/catalog/imports",
        ], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.stdout, "413", result.stderr)
        self.assertEqual(self.read_catalog(), before)
        failed = self.deliver(package, endpoint=f"https://localhost:{free_port()}")
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.read_catalog(), before)
        # Retrying the same retained package/run creates no replacement snapshot.
        self.assertEqual(self.deliver(package).returncode, 0)
        self.assertEqual(self.read_catalog(), before)


if __name__ == "__main__":
    unittest.main()
