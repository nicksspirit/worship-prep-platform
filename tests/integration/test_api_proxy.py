"""Test the production gateway with real Nginx and temporary HTTP backends.

Run with ``python tests/integration/test_api_proxy.py`` after installing Nginx.
"""

import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        self.respond(b"")

    def do_POST(self):
        if self.headers.get("Transfer-Encoding") == "chunked":
            chunks = []
            while size := int(self.rfile.readline().strip(), 16):
                chunks.append(self.rfile.read(size))
                self.rfile.read(2)
            self.rfile.readline()
            body = b"".join(chunks)
        else:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
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
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def serve_django():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Backend)
    server.backend = "django"
    server.serve_forever()


class ProxyTests(unittest.TestCase):
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
        cls.bolt = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        cls.bolt.backend = "bolt"
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, private_key)
        cls.bolt.socket = context.wrap_socket(cls.bolt.socket, server_side=True)
        threading.Thread(target=cls.bolt.serve_forever, daemon=True).start()
        cls.bolt_host = f"localhost:{cls.bolt.server_port}"
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

    def test_admin_keeps_original_host_and_https_scheme(self):
        status, _, body = self.request(
            "GET", "/admin/", headers={"Host": "app.rccgcm.org", "X-Forwarded-Proto": "https"}
        )
        result = json.loads(body)
        self.assertEqual(
            (status, result["backend"], result["host"], result["proto"]),
            (200, "django", "app.rccgcm.org", "https"),
        )

    def test_streamed_import_keeps_path_credentials_and_package(self):
        package = b"\x00\xffcatalog" * 300_000
        status, _, body = self.request(
            "POST", "/api/v1/catalog/imports?source=windows", body=iter([package]),
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

    def test_proxy_rejects_upstream_certificate_for_wrong_hostname(self):
        config = Path("/tmp/wpp-nginx.conf").read_text()
        probe = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        port = probe.server_port
        probe.server_close()
        config = config.replace(f"listen {self.port}", f"listen {port}")
        config = config.replace(self.bolt_host, f"127.0.0.1:{self.bolt.server_port}")
        config = config.replace("/tmp/wpp-nginx.pid", str(self.root / "bad-tls.pid"))
        config_path = self.root / "bad-tls.conf"
        config_path.write_text(config)
        process = subprocess.Popen(
            ["/usr/sbin/nginx", "-c", str(config_path), "-g", "daemon off;"],
            stdout=self.logs, stderr=self.logs,
        )
        try:
            for _ in range(100):
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
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


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve-django"]:
        serve_django()
    else:
        unittest.main()
