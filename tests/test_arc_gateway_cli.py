from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from domainfi_toolkit.cli import main


class ArcGatewayCliTests(unittest.TestCase):
    def test_arc_gateway_verify_posts_payment_to_configured_verifier(self) -> None:
        captured = {}

        class FakeVerifier:
            def __init__(self, base_url, *, api_key=None, timeout_seconds=20):
                captured["base_url"] = base_url
                captured["api_key"] = api_key
                captured["timeout_seconds"] = timeout_seconds

            def verify(self, *, payment, resource, amount_microusd, pay_to):
                captured["verify"] = {
                    "payment": payment,
                    "resource": resource,
                    "amount_microusd": amount_microusd,
                    "pay_to": pay_to,
                }
                return {"paid": True, "status": "accepted", "production_verifier": "circle_gateway"}

        out = io.StringIO()
        with patch("domainfi_toolkit.cli.CircleGatewayVerifier", FakeVerifier):
            rc = main(
                [
                    "arc-gateway-verify",
                    "--payment",
                    "opaque-proof",
                    "--gateway-url",
                    "https://gateway.example.test/v1",
                    "--gateway-api-key",
                    "testtok",
                    "--gateway-timeout",
                    "3",
                    "--json",
                ],
                stdout=out,
            )
        self.assertEqual(rc, 0)
        self.assertEqual(captured["base_url"], "https://gateway.example.test/v1")
        self.assertEqual(captured["api_key"], "testtok")
        self.assertEqual(captured["timeout_seconds"], 3)
        self.assertEqual(captured["verify"]["payment"], "opaque-proof")
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["paid"])

    def test_arc_gateway_verify_requires_url(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(["arc-gateway-verify", "--payment", "opaque-proof"], stdout=out)
        self.assertEqual(rc, 2)
        self.assertIn("--gateway-url", err.getvalue())


if __name__ == "__main__":
    unittest.main()
