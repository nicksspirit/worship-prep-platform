"""Exercise the production launcher with real Nginx and Gunicorn on Linux.

Run with ``python tests/integration/test_shutdown.py`` after installing both.
"""

import concurrent.futures
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import signal
import ssl
import subprocess
import tempfile
import threading
import time
import unittest


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        source = Path(__file__).resolve().parents[2]
        (self.root / "deploy").mkdir()
        (self.root / "backend").mkdir()
        (self.root / "backend/__init__.py").touch()
        shutil.copy(source / "deploy/start-django.sh", self.root / "deploy")
        certificate = self.root / "certificate.pem"
        key = self.root / "key.pem"
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", str(key), "-out", str(certificate), "-days", "1",
                "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
            ],
            check=True, capture_output=True,
        )
        template = (source / "deploy/nginx.conf.template").read_text()
        (self.root / "deploy/nginx.conf.template").write_text(
            template.replace("/etc/ssl/certs/ca-certificates.crt", str(certificate))
        )
        root = self.root

        class BoltHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                (root / "started").touch()
                while not (root / "release").exists():
                    time.sleep(0.02)
                self.send_response(200)
                self.send_header("Content-Length", "8")
                self.end_headers()
                self.wfile.write(b"finished")

        self.bolt = ThreadingHTTPServer(("127.0.0.1", 0), BoltHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        self.bolt.socket = context.wrap_socket(self.bolt.socket, server_side=True)
        self.addCleanup(self.bolt.server_close)
        self.addCleanup(self.bolt.shutdown)
        threading.Thread(target=self.bolt.serve_forever, daemon=True).start()
        # A real Gunicorn worker holds the response until the test releases it.
        (self.root / "backend/wsgi.py").write_text('''
from pathlib import Path
import time

def application(environ, start_response):
    path = environ["PATH_INFO"]
    if path != "/health/":
        Path("started").touch()
        while not Path("release").exists():
            time.sleep(0.02)
    start_response("200 OK", [("Content-Length", "8")])
    return [b"finished"]
''')
        self.logs = (self.root / "logs").open("w+")
        self.addCleanup(self.logs.close)
        self.process = subprocess.Popen(
            ["bash", str(self.root / "deploy/start-django.sh")],
            env={
                **os.environ,
                "DATABASE_URL": "postgresql://unused",
                "BOLT_UPSTREAM_URL": f"https://localhost:{self.bolt.server_port}",
                "WEB_CONCURRENCY": "1",
                "PORT": "8080",
            },
            stdout=self.logs, stderr=self.logs,
        )
        self.addCleanup(self.stop)
        self.wait_for(lambda: self.responds(), "launcher did not start")
        self.pids = self.descendants(self.process.pid)

    def stop(self):
        (self.root / "release").touch()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        # Also clean up after a red test leaves unmanaged descendants alive.
        for pid in getattr(self, "pids", []):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    @staticmethod
    def descendants(parent):
        children = []
        for path in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = path.read_text().split(") ", 1)[1].split()
                if int(fields[1]) == parent:
                    pid = int(path.parent.name)
                    children.extend([pid, *ShutdownTests.descendants(pid)])
            except FileNotFoundError:
                pass
        return children

    def wait_for(self, condition, message):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.02)
        self.logs.seek(0)
        self.fail(f"{message}\n{self.logs.read()}")

    def request(self, path="/health/"):
        connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=12)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def responds(self):
        try:
            return self.request() == (200, b"finished")
        except OSError:
            return False

    def assert_stopped(self):
        self.assertFalse(self.responds())
        live = []
        for pid in self.pids:
            try:
                state = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[0]
                if state != "Z":
                    live.append(pid)
            except FileNotFoundError:
                pass
        self.assertEqual(live, [], "supervised descendants remain running")

    def test_active_django_request_finishes_on_sigterm(self):
        self.finish_request("/short/")

    def test_active_bolt_request_finishes_on_sigterm(self):
        self.finish_request("/api/short/")

    def finish_request(self, path):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            response = executor.submit(self.request, path)
            self.wait_for(lambda: (self.root / "started").exists(), "request did not start")

            self.process.terminate()

            time.sleep(0.2)
            self.assertFalse(self.responds(), "shutdown must stop accepting new work")
            (self.root / "release").touch()
            self.assertEqual(response.result(timeout=5), (200, b"finished"))
        self.assertEqual(self.process.wait(timeout=10), 0)
        self.assert_stopped()

    def test_stalled_request_is_forced_closed_before_cloud_run_deadline(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            response = executor.submit(self.request, "/stall/")
            self.wait_for(lambda: (self.root / "started").exists(), "request did not start")
            started = time.monotonic()

            self.process.terminate()

            self.assertEqual(self.process.wait(timeout=9.5), 0)
            self.assertGreaterEqual(time.monotonic() - started, 7)
            self.assertLess(time.monotonic() - started, 9.5)
            with self.assertRaises((OSError, http.client.HTTPException)):
                response.result(timeout=1)
        self.assert_stopped()

    def fail_server(self, name, signal_number):
        children = Path(
            f"/proc/{self.process.pid}/task/{self.process.pid}/children"
        ).read_text().split()
        pid = next(
            int(pid) for pid in children
            if name in Path(f"/proc/{pid}/cmdline").read_text()
        )

        os.kill(pid, signal_number)

        self.assertEqual(self.process.wait(timeout=9.5), 1)
        self.assert_stopped()

    def test_gunicorn_clean_exit_is_reported_as_service_failure(self):
        self.fail_server("gunicorn", signal.SIGTERM)

    def test_nginx_clean_exit_is_reported_as_service_failure(self):
        self.fail_server("nginx", signal.SIGTERM)

    def test_killed_gunicorn_master_leaves_no_running_workers(self):
        self.fail_server("gunicorn", signal.SIGKILL)

    def test_killed_nginx_master_leaves_no_running_workers(self):
        self.fail_server("nginx", signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
