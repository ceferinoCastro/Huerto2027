"""Servidor estático local con proxy GET de solo lectura hacia FastAPI."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PORT = 5500
BACKEND_BASE_URL = "http://127.0.0.1:8000"


class FrontendHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy_get()
            return
        super().do_GET()

    def _proxy_get(self) -> None:
        request = Request(
            BACKEND_BASE_URL + self.path,
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=30) as response:
                self._send_proxy_response(
                    response.status,
                    response.headers.get("Content-Type", "application/json"),
                    response.read(),
                )
        except HTTPError as error:
            self._send_proxy_response(
                error.code,
                error.headers.get("Content-Type", "application/json"),
                error.read(),
            )
        except URLError:
            self._send_proxy_response(
                502,
                "application/json; charset=utf-8",
                b'{"detail":"FastAPI no esta disponible"}',
            )

    def _send_proxy_response(
        self, status: int, content_type: str, body: bytes
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class IPv6LoopbackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

if __name__ == "__main__":
    ipv4_server = ThreadingHTTPServer(("127.0.0.1", PORT), FrontendHandler)
    ipv6_server = IPv6LoopbackServer(("::1", PORT), FrontendHandler)
    ipv6_thread = threading.Thread(
        target=ipv6_server.serve_forever,
        daemon=True,
    )
    ipv6_thread.start()
    print(f"Frontend disponible en http://localhost:{PORT}/")
    try:
        ipv4_server.serve_forever()
    finally:
        ipv4_server.server_close()
        ipv6_server.shutdown()
        ipv6_server.server_close()
