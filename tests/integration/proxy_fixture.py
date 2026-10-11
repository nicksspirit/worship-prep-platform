"""A trusted TLS HTTP/2 frontend for local Cloud Run transport simulations."""

import socket
import subprocess
import time


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class TLSProxy:
    def __init__(self, root, upstream, certificate, key, port=None, http2_upstream=False):
        self.port = port or free_port()
        self.access_log = root / f"tls-{self.port}.log"
        config = root / f"tls-{self.port}.conf"
        config.write_text(f'''
worker_processes 1;
pid {root}/tls-{self.port}.pid;
error_log stderr;
events {{ worker_connections 1024; }}
http {{
    log_format protocol '$server_protocol';
    access_log {self.access_log} protocol;
    client_max_body_size 130m;
    client_body_temp_path {root}/body-{self.port};
    proxy_temp_path {root}/proxy-{self.port};
    fastcgi_temp_path {root}/fastcgi-{self.port};
    uwsgi_temp_path {root}/uwsgi-{self.port};
    scgi_temp_path {root}/scgi-{self.port};
    upstream fixture {{ server 127.0.0.1:{upstream}; keepalive 16; }}
    server {{
        listen {self.port} ssl;
        http2 on;
        ssl_certificate {certificate};
        ssl_certificate_key {key};
        location / {{
            proxy_pass http://fixture;
            proxy_http_version {"2" if http2_upstream else "1.1"};
            proxy_set_header Connection "";
            proxy_set_header Host $http_host;
            proxy_request_buffering off;
            proxy_read_timeout 600s;
            add_header X-Upstream-Protocol $server_protocol always;
        }}
    }}
}}
''')
        self.process = subprocess.Popen(
            ["nginx", "-e", "stderr", "-c", str(config), "-g", "daemon off;"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        for _ in range(100):
            if self.process.poll() is not None:
                raise RuntimeError(self.process.stderr.read().decode())
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    return
            except OSError:
                time.sleep(0.05)
        self.close()
        raise RuntimeError("TLS HTTP/2 fixture did not start")

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=10)
        self.process.stderr.close()
