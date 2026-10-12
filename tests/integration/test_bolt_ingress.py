"""Test the Bolt HTTP/2 ingress with real Nginx and a temporary HTTP backend.

Run with ``python tests/integration/test_bolt_ingress.py`` after installing Nginx.
"""

import hashlib
import http.client
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from string import Template

import yaml
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from proxy_fixture import free_port


class Backend(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith(("/api/log-contract", "/log-contract")):
            body = json.dumps({"request_id": self.headers.get("X-Request-ID"), "trace_context": self.headers.get("X-Cloud-Trace-Context")}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.respond(b"")

    def do_POST(self):
        if self.headers.get("Transfer-Encoding") == "chunked":
            chunks = []
            while size := int(self.rfile.readline().strip(), 16):
                chunks.append(self.rfile.read(size))
                self.server.received_chunk.set()
                self.rfile.read(2)
            self.rfile.readline()
            body = b"".join(chunks)
        else:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if client := getattr(self.server, "catalog_client", None):
            result = client.post(self.path, content=body, headers=dict(self.headers))
            self.send_response(result.status_code)
            self.send_header("Content-Length", str(len(result.content)))
            self.end_headers()
            self.wfile.write(result.content)
        else:
            self.respond(body)

    def respond(self, body):
        response = json.dumps(
            {
                "backend": self.server.backend,
                "path": self.path,
                "host": self.headers.get("Host"),
                "proto": self.headers.get("X-Forwarded-Proto"),
                "authorization": self.headers.get("Authorization"),
                "trigger": self.headers.get("X-Catalog-Import-Trigger"),
                "content_type": self.headers.get("Content-Type"),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Backend-Connection", str(self.client_address[1]))
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class BoltIngressTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        source = Path(__file__).resolve().parents[2]
        cls.addClassCleanup(cls.directory.cleanup)
        cls.bolt = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        cls.addClassCleanup(cls.bolt.server_close)
        cls.addClassCleanup(cls.bolt.shutdown)
        cls.bolt.backend = "bolt"
        cls.bolt.received_chunk = threading.Event()
        threading.Thread(target=cls.bolt.serve_forever, daemon=True).start()
        cls.port = free_port()
        cls.bolt_host = "api.rccgcm.org"
        logging = (source / "deploy/nginx-logging.conf.template").read_text()
        (cls.root / "logging.conf").write_text(logging.replace(
            "${GCP_PROJECT_ID}", "wpp-test-project",
        ))
        cls.template = (source / "deploy/nginx-bolt.conf.template").read_text()
        cls.template = cls.template.replace("/tmp/wpp-nginx", str(cls.root / "nginx"))
        cls.template = cls.template.replace(
            str(cls.root / "nginx-logging.conf"), str(cls.root / "logging.conf"),
        )
        config = cls.root / "nginx.conf"
        config.write_text(cls.template.replace("${PORT}", str(cls.port)).replace(
            "127.0.0.1:8000", f"127.0.0.1:{cls.bolt.server_port}",
        ))
        cls.logs = (cls.root / "logs").open("a+")
        cls.addClassCleanup(cls.logs.close)
        cls.process = subprocess.Popen(
            ["nginx", "-e", "stderr", "-c", str(config), "-g", "daemon off;"],
            stdout=cls.logs, stderr=cls.logs,
        )
        cls.addClassCleanup(cls.stop_process)
        for _ in range(100):
            try:
                if cls.request("GET", "/admin/")[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.05)
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.logs.seek(0)
        raise AssertionError(cls.logs.read())

    @classmethod
    def stop_process(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)

    @classmethod
    def request(cls, method, path, body=None, headers=None, chunked=False):
        connection = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        connection.request(method, path, body=body, headers={"Host": cls.bolt_host, **(headers or {})}, encode_chunked=chunked)
        response = connection.getresponse()
        result = response.status, {
            name.title(): value for name, value in response.getheaders()
        }, response.read()
        connection.close()
        return result

    def test_json_access_logs_share_forwarded_identity_without_secrets(self):
        trace = "0123456789abcdef0123456789abcdef/42;o=1"
        for prefix in ("/api", ""):
            with self.subTest(prefix=prefix):
                status, _, body = self.request("GET", prefix + "/log-contract/%22%5C%09?key=private-query", headers={"X-Request-ID": "proxy-123", "X-Cloud-Trace-Context": trace, "Authorization": "Bearer private-key"})
                result = json.loads(body)
                self.assertEqual((status, result), (200, {"request_id": "proxy-123", "trace_context": trace}))
        time.sleep(0.1)
        self.logs.seek(0)
        output = self.logs.read()
        events = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
        correlated = [event for event in events if event.get("request_id") == "proxy-123"]
        self.assertEqual(len(correlated), 2)
        for event in correlated:
            self.assertEqual(event["logging.googleapis.com/trace"], "projects/wpp-test-project/traces/0123456789abcdef0123456789abcdef")
            self.assertEqual((event["method"], event["status"]), ("GET", 200))
            self.assertGreaterEqual(float(event["duration"]), 0)
            self.assertEqual(event["upstream_status"], "200")
        self.assertNotIn("private-query", output)
        self.assertNotIn("private-key", output)

    @unittest.skipUnless(importlib.util.find_spec("django_bolt"), "Requires the project Python runtime")
    def test_proxy_and_real_bolt_dispatch_log_the_same_cloud_trace(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
        os.environ.setdefault("DJANGO_ENV", "test")
        django.setup()
        from django.test import override_settings
        from django_bolt.testing import TestClient

        from apps.catalog.api import api
        from apps.common.tests.test_request_logging import capture_logs

        with override_settings(GCP_PROJECT_ID="wpp-test-project"), capture_logs() as logs, TestClient(api, read_django_settings=False) as client:
            self.bolt.catalog_client = client
            try:
                status, _, _ = self.request("POST", "/api/v1/catalog/imports?key=private-query", headers={"X-Request-ID": "cross-service-123", "X-Cloud-Trace-Context": "0123456789abcdef0123456789abcdef/42;o=1", "Authorization": "Bearer private-key"})
            finally:
                del self.bolt.catalog_client
        self.assertEqual(status, 422)
        time.sleep(0.1)
        self.logs.seek(0)
        proxy_events = [json.loads(line) for line in self.logs.read().splitlines() if line.startswith("{")]
        bolt_events = [json.loads(line) for line in logs.getvalue().splitlines()]
        for events in (proxy_events, bolt_events):
            event = next(event for event in events if event.get("request_id") == "cross-service-123")
            self.assertEqual((event["status"], event["logging.googleapis.com/trace"]), (422, "projects/wpp-test-project/traces/0123456789abcdef0123456789abcdef"))
        self.assertNotIn("private-query", logs.getvalue())
        self.assertNotIn("private-key", logs.getvalue())

    def test_early_rejection_is_valid_json_without_an_upstream(self):
        status, _, _ = self.request("POST", "/api/v1/catalog/imports?key=private-query", headers={"Content-Length": str(131 * 1024 * 1024), "X-Request-ID": "early-rejection-123"})
        self.assertEqual(status, 413)
        time.sleep(0.1)
        self.logs.seek(0)
        output = self.logs.read()
        events = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
        event = next(event for event in events if event.get("request_id") == "early-rejection-123")
        self.assertEqual(event["status"], 413)
        self.assertEqual(event["upstream_status"], "")
        self.assertEqual(event["upstream_duration"], "")
        self.assertNotIn("private-query", output)

    def test_proxy_replaces_untrusted_correlation_with_bounded_identity(self):
        status, _, body = self.request("GET", "/api/log-contract", headers={"X-Request-ID": 'bad"\\' * 100, "X-Cloud-Trace-Context": "untrusted-trace"})
        result = json.loads(body)
        self.assertEqual(status, 200)
        self.assertRegex(result["request_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(result["trace_context"], result["request_id"] + "/0;o=0")


    def test_response_does_not_expose_nginx_version(self):
        status, headers, _ = self.request("GET", "/api/v1/docs")

        self.assertEqual((status, headers["Server"]), (200, "nginx"))


    def test_streamed_import_keeps_path_credentials_and_package(self):
        package = (
            b'--fixture\r\nContent-Disposition: form-data; name="package"; '
            b'filename="catalog.zip"\r\nContent-Type: application/zip\r\n\r\n'
            + b"\x00\xffcatalog" * 300_000
            + b"\r\n--fixture--\r\n"
        )
        self.bolt.received_chunk.clear()

        def stream_package():
            yield package[:1_000_000]
            self.assertTrue(
                self.bolt.received_chunk.wait(timeout=5),
                "Bolt must receive the first chunk before the upload finishes",
            )
            yield package[1_000_000:]

        status, _, body = self.request(
            "POST", "/api/v1/catalog/imports?source=windows", body=stream_package(),
            headers={
                "Authorization": "Bearer routing-test-only",
                "X-Catalog-Import-Trigger": "scheduled",
                "Content-Type": "multipart/form-data; boundary=fixture",
            },
            chunked=True,
        )
        result = json.loads(body)
        self.assertEqual(
            (status, result),
            (200, {
                "backend": "bolt", "path": "/api/v1/catalog/imports?source=windows",
                "host": self.bolt_host, "proto": None,
                "authorization": "Bearer routing-test-only", "trigger": "scheduled",
                "content_type": "multipart/form-data; boundary=fixture",
                "sha256": hashlib.sha256(package).hexdigest(),
            }),
        )

    def test_bolt_ingress_accepts_cleartext_http2(self):
        result = subprocess.run(
            ["curl", "--http2-prior-knowledge", "--fail", "--silent", "--show-error",
             f"http://127.0.0.1:{self.port}/api/v1/docs"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["backend"], "bolt")

    def test_service_manifest_rendering_keeps_application_secrets_in_bolt(self):
        source = Path(__file__).resolve().parents[2]
        build = yaml.safe_load((source / "cloudbuild.yaml").read_text())
        deployment = next(step for step in build["steps"] if step["id"] == "deploy-bolt")
        renderer = deployment["args"][1].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "service.json"
            renderer = renderer.replace("/tmp/wpp-api-service.json", str(output))
            ordinary_value = 'Quoted "value" with a backslash \\ and\na second line'
            result = subprocess.run(
                [sys.executable, "-c", renderer], cwd=source,
                env={
                    **os.environ,
                    "API_NAME": "wpp-api", "PROJECT_ID": "wpp-test-project",
                    "RUNTIME_SA": "fixture@wpp-test-project.iam.gserviceaccount.com",
                    "INGRESS_IMAGE": "fixture-ingress", "PROD_IMAGE": "fixture-prod",
                    "SERVICE_ENV": f"^|^APP_NAME={ordinary_value}|BOLT_PORT=8000",
                    "SERVICE_SECRETS": "DATABASE_URL=database-url:latest,SECRET_KEY=django-key:7",
                }, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(output.read_text())
        containers = {item["name"]: item for item in
                      manifest["spec"]["template"]["spec"]["containers"]}
        self.assertEqual(containers["ingress"]["env"],
                         [{"name": "GCP_PROJECT_ID", "value": "wpp-test-project"}])
        self.assertEqual(containers["bolt"]["env"], [
            {"name": "APP_NAME", "value": ordinary_value},
            {"name": "BOLT_PORT", "value": "8000"},
            {"name": "DATABASE_URL", "valueFrom": {
                "secretKeyRef": {"name": "database-url", "key": "latest"}}},
            {"name": "SECRET_KEY", "valueFrom": {
                "secretKeyRef": {"name": "django-key", "key": "7"}}},
        ])

    def test_startup_probe_rejects_open_proxy_until_backend_is_listening(self):
        source = Path(__file__).resolve().parents[2]
        build = yaml.safe_load((source / "cloudbuild.yaml").read_text())
        deployment = next(step for step in build["steps"] if step["id"] == "deploy-bolt")
        self.assertIn("deploy/api-service.json.template", "\n".join(deployment["args"]))
        values = {
            "API_NAME": "wpp-api", "PROJECT_ID": "wpp-test-project",
            "RUNTIME_SA": "fixture@wpp-test-project.iam.gserviceaccount.com",
            "INGRESS_IMAGE": "fixture-ingress", "PROD_IMAGE": "fixture-prod",
            "BOLT_ENV": [],
        }
        manifest = json.loads(Template(
            (source / "deploy/api-service.json.template").read_text()
        ).substitute({key: json.dumps(value) for key, value in values.items()}))
        template = manifest["spec"]["template"]
        self.assertEqual(json.loads(template["metadata"]["annotations"][
            "run.googleapis.com/container-dependencies"]), {"ingress": ["bolt"]})
        containers = {container["name"]: container
                      for container in template["spec"]["containers"]}
        self.assertEqual(set(containers), {"ingress", "bolt"})
        self.assertEqual(containers["ingress"]["ports"],
                         [{"name": "h2c", "containerPort": 8080}])
        self.assertNotIn("ports", containers["bolt"])
        self.assertEqual(containers["ingress"]["env"],
                         [{"name": "GCP_PROJECT_ID", "value": "wpp-test-project"}])
        self.assertEqual(containers["bolt"]["args"], ["deploy/start-bolt.sh"])
        for name, port in (("ingress", 8080), ("bolt", 8000)):
            self.assertEqual(containers[name]["startupProbe"]["httpGet"],
                             {"path": "/api/v1/docs", "port": port})
        path = containers["ingress"]["startupProbe"]["httpGet"]["path"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            port, backend_port = free_port(), free_port()
            config = root / "nginx.conf"
            config.write_text(self.template.replace(str(self.root / "nginx"),
                                                   str(root / "nginx"))
                              .replace("${PORT}", str(port))
                              .replace("127.0.0.1:8000", f"127.0.0.1:{backend_port}"))
            process = subprocess.Popen(
                ["nginx", "-e", "stderr", "-c", str(config), "-g", "daemon off;"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                for _ in range(100):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=1):
                            break
                    except OSError:
                        time.sleep(0.02)
                else:
                    self.fail("Cold-start proxy did not open its ingress port")
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                try:
                    connection.request("GET", path)
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 502)

                    backend = ThreadingHTTPServer(("127.0.0.1", backend_port), Backend)
                    backend.backend = "bolt"
                    threading.Thread(target=backend.serve_forever, daemon=True).start()
                    try:
                        connection.request("GET", path)
                        response = connection.getresponse()
                        response.read()
                        self.assertEqual(response.status, 200)
                        connection.request("OPTIONS", "/api/v1/catalog/imports")
                        response = connection.getresponse()
                        response.read()
                        self.assertEqual(response.status, 204)
                    finally:
                        backend.shutdown()
                        backend.server_close()
                finally:
                    connection.close()
            finally:
                process.terminate()
                process.wait(timeout=10)

    def test_import_options_reaches_bolt(self):
        status, headers, body = self.request("OPTIONS", "/api/v1/catalog/imports")
        self.assertEqual((status, headers["Allow"], body), (204, "POST, OPTIONS", b""))


if __name__ == "__main__":
    unittest.main()
