"""Opt-in HTTP/DOM test: JSDOM_PATH points to an installed jsdom package."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer

import pytest
import uvicorn

from tests.test_campaign_repair import safe_app

ROOT = Path(__file__).resolve().parents[2]


def test_campaign_dom_proxy_fastapi_flow():
    if not os.environ.get("JSDOM_PATH"):
        pytest.skip("Set JSDOM_PATH to run the controlled DOM/HTTP integration")
    app, db = safe_app()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    backend_port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    spec = importlib.util.spec_from_file_location("campaign_test_proxy", ROOT / "frontend2/servidor.py")
    proxy_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy_module)
    proxy_module.BACKEND_BASE_URL = f"http://127.0.0.1:{backend_port}"
    handler = partial(proxy_module.FrontendHandler, directory=str(ROOT / "frontend2"))
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            time.sleep(.01)
        assert server.started
        result = subprocess.run(["node", str(ROOT / "backend/tests/campaign_flow.mjs")], cwd=ROOT,
            env={**os.environ, "CAMPAIGN_TEST_ORIGIN": f"http://127.0.0.1:{proxy.server_port}"},
            text=True, capture_output=True, timeout=45)
        print(result.stdout)
        assert result.returncode == 0, result.stderr + result.stdout
        assert db.collection.documents[0]["estado"] == "finalizada"
        assert len(db.collection.writes) == 2
        assert db.collection.documents[0]["mediciones_ids"] == ["medicion-intacta"]
        assert db.measurements == {"lecturas": [{"valor": 12}], "mediciones_hanna": [{"ph": 7}],
                                  "mediciones_plantas": [{"altura_cm": 15}]}
    finally:
        proxy.shutdown()
        proxy.server_close()
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
