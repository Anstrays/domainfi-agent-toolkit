from __future__ import annotations

import importlib.util
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "examples" / "arc-x402-paid-agent" / "server.py"


def _load_server_module():
    spec = importlib.util.spec_from_file_location("arc_x402_paid_agent_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load arc x402 paid-agent server example")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArcX402PaidAgentExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server_module = _load_server_module()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), cls.server_module.PaidDiscoveryHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        address = cls.httpd.server_address
        cls.url = f"http://{address[0]}:{address[1]}/scan"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def _get_json(self, payment: str | None = None) -> tuple[int, dict]:
        headers = {}
        if payment:
            headers["X-Payment"] = payment
        request = Request(self.url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - local test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_scan_requires_payment_then_returns_paid_opportunities(self) -> None:
        status, challenge = self._get_json()
        self.assertEqual(status, 402)
        self.assertEqual(challenge["error"], "payment_required")
        self.assertIn("X-Payment", challenge["instructions"])

        status, payload = self._get_json(payment="x402-test:domainfi.discovery.scan:25000")
        self.assertEqual(status, 200)
        self.assertTrue(payload["payment"]["paid"])
        self.assertEqual(payload["payment"]["asset"], "USDC")
        self.assertGreater(len(payload["opportunities"]), 0)
        self.assertGreater(payload["unit_economics"]["gross_margin_microusd"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
