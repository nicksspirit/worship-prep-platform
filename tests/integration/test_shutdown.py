"""Exercise production launchers with real Gunicorn, Bolt and Nginx on Linux.

Run with ``python tests/integration/test_shutdown.py`` in the production-compatible Docker test image.
"""

import concurrent.futures
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from proxy_fixture import free_port


class ShutdownTests(unittest.TestCase):
    launcher = "start-django.sh"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        source = Path(__file__).resolve().parents[2]
        (self.root / "deploy").mkdir()
        (self.root / "backend").mkdir()
        (self.root / "backend/__init__.py").touch()
        # Exercise the actual Gunicorn launcher with a minimal WSGI app.
        (self.root / "backend/gunicorn.py").write_text(
            "accesslog = None\nerrorlog = '-'\ncontrol_socket_disable = True\n"
        )
        shutil.copy(source / "deploy" / self.launcher, self.root / "deploy")
        self.port = free_port()
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
        if self.launcher == "start-bolt.sh":
            shutil.copy(source / "manage.py", self.root)
            (self.root / "fixture_urls.py").write_text("urlpatterns = []\n")
            (self.root / "fixture_settings.py").write_text(
                'SECRET_KEY = "shutdown-fixture"\n'
                'INSTALLED_APPS = ["django_bolt"]\n'
                'BOLT_API = ["fixture_api:api"]\n'
                'ROOT_URLCONF = "fixture_urls"\n'
                'DEBUG = False\n'
                'ALLOWED_HOSTS = ["*"]\n'
            )
            (self.root / "fixture_api.py").write_text('''
import asyncio
from pathlib import Path
from django_bolt import BoltAPI, Response

api = BoltAPI(enable_logging=False)

@api.get("/health/")
async def health():
    return Response(b"finished", media_type="text/plain")

@api.get("/short/")
@api.get("/stall/")
async def hold_request():
    Path("started").touch()
    while not Path("release").exists():
        await asyncio.sleep(0.02)
    return Response(b"finished", media_type="text/plain")
''')
        self.logs = (self.root / "logs").open("w+")
        self.addCleanup(self.logs.close)
        self.process = subprocess.Popen(
            ["bash", str(self.root / "deploy" / self.launcher)],
            env={
                **os.environ,
                "DATABASE_URL": "postgresql://unused",
                "WEB_CONCURRENCY": "1",
                "PORT": str(self.port),
                "BOLT_PORT": str(self.port),
                "DJANGO_SETTINGS_MODULE": "fixture_settings",
                "PYTHONPATH": str(self.root),
            },
            stdout=self.logs, stderr=self.logs,
        )
        self.addCleanup(self.stop)
        self.wait_for(lambda: self.responds(), "launcher did not start", timeout=30)
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

    def wait_for(self, condition, message, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            if self.process.poll() is not None:
                break
            time.sleep(0.02)
        self.logs.seek(0)
        self.fail(f"{message}\n{self.logs.read()}")

    def request(self, path="/health/"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=12)
        try:
            connection.request("GET", path.rstrip("/") if self.launcher == "start-bolt.sh" else path)
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
        deadline = time.monotonic() + 1
        while True:
            live = []
            for pid in self.pids:
                try:
                    state = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[0]
                    if state != "Z":
                        live.append(pid)
                except FileNotFoundError:
                    pass
            if not live or time.monotonic() >= deadline:
                break
            time.sleep(0.02)
        self.assertEqual(live, [], "Server workers remain running")

    def test_active_request_finishes_on_sigterm(self):
        self.finish_request("/short/")

    def finish_request(self, path):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            response = executor.submit(self.request, path)
            self.wait_for(lambda: (self.root / "started").exists(), "request did not start")

            self.process.terminate()

            time.sleep(0.2)
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

class BoltShutdownTests(ShutdownTests):
    launcher = "start-bolt.sh"


class NginxShutdownTests(ShutdownTests):
    launcher = "start-ingress.sh"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        source = Path(__file__).resolve().parents[2]
        root = self.root

        class Backend(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path != "/health/":
                    (root / "started").touch()
                    while not (root / "release").exists():
                        time.sleep(0.02)
                try:
                    self.send_response(200)
                    self.send_header("Content-Length", "8")
                    self.end_headers()
                    self.wfile.write(b"finished")
                except BrokenPipeError:
                    pass

        backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        self.addCleanup(backend.server_close)
        self.addCleanup(backend.shutdown)
        threading.Thread(target=backend.serve_forever, daemon=True).start()
        self.port = free_port()
        config = (source / "deploy/nginx-bolt.conf.template").read_text()
        config = (config.replace("/tmp/wpp-nginx", str(root / "nginx"))
                  .replace("${PORT}", str(self.port))
                  .replace("127.0.0.1:8000", f"127.0.0.1:{backend.server_port}"))
        (root / "nginx-logging.conf").write_text(
            (source / "deploy/nginx-logging.conf.template").read_text()
            .replace("${GCP_PROJECT_ID}", "wpp-test-project")
        )
        (root / "nginx.conf").write_text(config)
        # Official entrypoint execs Nginx after rendering; this fixture renders above.
        entrypoint = root / "docker-entrypoint.sh"
        entrypoint.write_text('#!/bin/sh\nexec "$@"\n')
        entrypoint.chmod(0o755)
        launcher = root / "start-ingress.sh"
        launcher.write_text(
            (source / "deploy/start-ingress.sh").read_text()
            .replace("/docker-entrypoint.sh", str(entrypoint))
            .replace("/tmp/wpp-nginx.conf", str(root / "nginx.conf"))
        )
        self.logs = (root / "logs").open("w+")
        self.addCleanup(self.logs.close)
        self.process = subprocess.Popen(
            ["sh", str(launcher)], stdout=self.logs, stderr=self.logs,
        )
        self.addCleanup(self.stop)
        self.wait_for(self.responds, "Nginx ingress did not start")
        self.pids = self.descendants(self.process.pid)


if __name__ == "__main__":
    unittest.main()
