"""Servidor local de frontend2 con proxy HTTP hacia FastAPI."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PORT = 5600
BACKEND_BASE_URL = "http://127.0.0.1:8000"
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
DEFAULT_TIMEOUT_SECONDS = 30
HANNA_IMPORT_TIMEOUT_SECONDS = 300


class FrontendHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        # frontend2 se usa durante desarrollo: evitamos que el navegador conserve
        # versiones anteriores del formulario o de sus modulos JavaScript.
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_PATCH(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy_request()
        elif self.command == "GET":
            super().do_GET()
        else:
            self.send_error(405, "Method Not Allowed")

    def _proxy_request(self) -> None:
        if self.command not in ALLOWED_METHODS:
            self.send_error(405, "Method Not Allowed")
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else None
        request = Request(
            BACKEND_BASE_URL + self.path,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": self.headers.get("Content-Type", "application/json"),
            },
            method=self.command,
        )
        timeout = (
            HANNA_IMPORT_TIMEOUT_SECONDS
            if self.path.startswith("/api/v1/mediciones-hanna/importar-csv")
            else DEFAULT_TIMEOUT_SECONDS
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                self._send_response(response.status, response.headers, response.read())
        except HTTPError as error:
            self._send_response(error.code, error.headers, error.read())
        except (TimeoutError, socket.timeout):
            self._send_json_error(
                504,
                "FastAPI agotó el tiempo de espera al procesar el archivo. "
                "La importación puede seguir en curso; revise el resumen antes de reintentarla.",
            )
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                self._send_json_error(
                    504,
                    "FastAPI agotó el tiempo de espera. Revise el estado de la carga antes de reintentar.",
                )
            else:
                self._send_json_error(502, "FastAPI no está disponible en http://127.0.0.1:8000")

    def _send_json_error(self, status: int, detail: str) -> None:
        import json

        self._send_response(
            status,
            {"Content-Type": "application/json; charset=utf-8"},
            json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8"),
        )

    def _send_response(self, status: int, headers, body: bytes) -> None:
        content_type = headers.get("Content-Type", "application/json; charset=utf-8")
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
    threading.Thread(target=ipv6_server.serve_forever, daemon=True).start()
    print(f"frontend2 disponible en http://localhost:{PORT}/")
    try:
        ipv4_server.serve_forever()
    finally:
        ipv4_server.server_close()
        ipv6_server.shutdown()
        ipv6_server.server_close()
