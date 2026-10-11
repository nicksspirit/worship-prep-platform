"""Test the production gateway with real Nginx and temporary HTTP backends.

Run with ``python tests/integration/test_api_proxy.py`` after installing Nginx.
"""

import hashlib
import http.client
import importlib.util
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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


def serve_django():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Backend)
    server.backend = "django"
    server.serve_forever()


class ProxyTests(unittest.TestCase):
    use_default_https_port = False

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        source = Path(__file__).resolve().parents[2]
        (cls.root / "deploy").mkdir()
        shutil.copy(source / "deploy/start-django.sh", cls.root / "deploy")
        certificate = cls.root / "certificate.pem"
        private_key = cls.root / "private-key.pem"
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", str(private_key), "-out", str(certificate), "-days", "1",
                "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
            ],
            check=True, capture_output=True,
        )
        template = (source / "deploy/nginx.conf.template").read_text()
        (cls.root / "deploy/nginx.conf.template").write_text(
            template.replace("/etc/ssl/certs/ca-certificates.crt", str(certificate))
        )
        cls.bolt = ThreadingHTTPServer(
            ("127.0.0.1", 443 if cls.use_default_https_port else 0), Backend
        )
        cls.bolt.backend = "bolt"
        cls.bolt.received_chunk = threading.Event()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, private_key)
        cls.bolt.socket = context.wrap_socket(cls.bolt.socket, server_side=True)
        threading.Thread(target=cls.bolt.serve_forever, daemon=True).start()
        cls.bolt_host = (
            "localhost" if cls.use_default_https_port else f"localhost:{cls.bolt.server_port}"
        )
        # Only Gunicorn is replaced; the production launcher and Nginx are real.
        (cls.root / "gunicorn").write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{Path(__file__).resolve()}" --serve-django\n'
        )
        (cls.root / "gunicorn").chmod(0o755)
        probe = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        cls.port = probe.server_port
        probe.server_close()
        cls.logs = (cls.root / "logs").open("w+")
        cls.process = subprocess.Popen(
            ["bash", str(cls.root / "deploy/start-django.sh")],
            env={
                **os.environ,
                "PATH": f"{cls.root}:/usr/sbin:{os.environ['PATH']}",
                "DATABASE_URL": "postgresql://unused",
                "BOLT_UPSTREAM_URL": f"https://{cls.bolt_host}",
                "PORT": str(cls.port),
                "GCP_PROJECT_ID": "wpp-test-project",
            },
            stdout=cls.logs, stderr=cls.logs,
        )
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
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.bolt.shutdown()
        cls.bolt.server_close()
        cls.logs.close()
        cls.directory.cleanup()

    @classmethod
    def request(cls, method, path, body=None, headers=None, chunked=False):
        connection = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        connection.request(method, path, body=body, headers=headers or {}, encode_chunked=chunked)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
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

    def test_django_routes_keep_original_host_and_https_scheme(self):
        for path in ("/", "/admin/", "/accounts/google/login/", "/install"):
            with self.subTest(path=path):
                status, _, body = self.request(
                    "GET", path,
                    headers={"Host": "app.rccgcm.org", "X-Forwarded-Proto": "https"},
                )
                result = json.loads(body)
                self.assertEqual(
                    (
                        status, result["backend"], result["path"],
                        result["host"], result["proto"],
                    ),
                    (200, "django", path, "app.rccgcm.org", "https"),
                )

    def test_response_does_not_expose_nginx_version(self):
        status, headers, _ = self.request("GET", "/admin/")

        self.assertEqual((status, headers["Server"]), (200, "nginx"))

    def test_repeated_api_requests_reuse_upstream_connection(self):
        responses = [self.request("GET", "/api/v1/catalog/songs") for _ in range(3)]

        self.assertEqual([response[0] for response in responses], [200, 200, 200])
        connections = {response[1]["X-Backend-Connection"] for response in responses}
        self.assertEqual(len(connections), 1)

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

    def test_import_options_reaches_bolt(self):
        status, headers, body = self.request("OPTIONS", "/api/v1/catalog/imports")
        self.assertEqual((status, headers["Allow"], body), (204, "POST, OPTIONS", b""))

    def test_launcher_rejects_an_insecure_upstream(self):
        result = subprocess.run(
            ["bash", str(self.root / "deploy/start-django.sh")],
            env={**os.environ, "DATABASE_URL": "unused", "BOLT_UPSTREAM_URL": "http://localhost"},
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must be an HTTPS origin", result.stderr)

    def test_proxy_rejects_invalid_upstream_certificates(self):
        rendered = Path("/tmp/wpp-nginx.conf").read_text()
        invalid_configs = {
            "wrong-hostname": rendered.replace(
                f"proxy_ssl_name {self.bolt_host};", "proxy_ssl_name wrong.example;"
            ),
            "untrusted-chain": rendered.replace(
                str(self.root / "certificate.pem"), "/etc/ssl/certs/ca-certificates.crt"
            ),
        }
        for failure, config in invalid_configs.items():
            with self.subTest(failure=failure):
                probe = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
                port = probe.server_port
                probe.server_close()
                config = config.replace(f"listen {self.port}", f"listen {port}")
                config = config.replace("/tmp/wpp-nginx.pid", str(self.root / f"{failure}.pid"))
                config_path = self.root / f"{failure}.conf"
                config_path.write_text(config)
                process = subprocess.Popen(
                    ["/usr/sbin/nginx", "-c", str(config_path), "-g", "daemon off;"],
                    stdout=self.logs, stderr=self.logs,
                )
                try:
                    for _ in range(100):
                        try:
                            connection = http.client.HTTPConnection(
                                "127.0.0.1", port, timeout=10
                            )
                            connection.request("OPTIONS", "/api/v1/catalog/imports")
                            response = connection.getresponse()
                            status = response.status
                            response.read()
                            connection.close()
                            break
                        except OSError:
                            time.sleep(0.05)
                    else:
                        self.fail("TLS test proxy did not start")
                    self.assertEqual(status, 502)
                finally:
                    process.terminate()
                    process.wait(timeout=10)

    def test_zz_launcher_stops_both_listeners_on_sigterm(self):
        self.process.terminate()
        self.assertEqual(self.process.wait(timeout=10), 0)
        for port in (self.port, 8000):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            with self.assertRaises(OSError):
                connection.request("GET", "/admin/")
            connection.close()


class DefaultHttpsPortTests(ProxyTests):
    """Exercise the same routes using the portless origin returned by Cloud Run."""

    use_default_https_port = True


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve-django"]:
        serve_django()
    else:
        unittest.main()
