from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from domainfi_toolkit.arc import CircleGatewayVerifier, build_gateway_verification_request


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class CircleGatewayVerifierTests(unittest.TestCase):
    def test_build_gateway_verification_request_shape_is_safe_and_explicit(self) -> None:
        payload = build_gateway_verification_request(
            payment="opaque-x402-proof",
            resource="domainfi.discovery.scan",
            amount_microusd=25000,
            pay_to="0x0000000000000000000000000000000000000000",
        )
        self.assertEqual(payload["network"], "arc-testnet")
        self.assertEqual(payload["chain_id"], 5042002)
        self.assertEqual(payload["asset"], "USDC")
        self.assertEqual(payload["asset_decimals"], 6)
        self.assertEqual(payload["payment"], "opaque-x402-proof")
        self.assertEqual(payload["gateway_domain"], 26)

    def test_verifier_posts_to_configured_gateway_and_returns_receipt(self) -> None:
        calls = []

        def fake_urlopen(request, timeout=0):
            calls.append((request.full_url, request.headers, json.loads(request.data.decode("utf-8")), timeout))
            return _FakeResponse({"paid": True, "receipt_id": "rcpt_123", "status": "accepted"})

        with patch("domainfi_toolkit.arc.urlopen", fake_urlopen):
            verifier = CircleGatewayVerifier(
                "https://gateway.example.test/v1",
                api_key="testtok",
                timeout_seconds=9,
            )
            receipt = verifier.verify(
                payment="opaque-x402-proof",
                resource="domainfi.discovery.scan",
                amount_microusd=25000,
                pay_to="0x0000000000000000000000000000000000000000",
            )

        self.assertTrue(receipt["paid"])
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(receipt["production_verifier"], "circle_gateway")
        self.assertEqual(calls[0][0], "https://gateway.example.test/v1/x402/verify")
        self.assertEqual(calls[0][1]["Authorization"], "Bearer testtok")
        self.assertEqual(calls[0][2]["resource"], "domainfi.discovery.scan")
        self.assertEqual(calls[0][3], 9)

    def test_verifier_redacts_secret_from_errors(self) -> None:
        def fake_urlopen(request, timeout=0):
            raise OSError("testtok exploded")

        with patch("domainfi_toolkit.arc.urlopen", fake_urlopen):
            verifier = CircleGatewayVerifier("https://gateway.example.test/v1", api_key="testtok")
            receipt = verifier.verify(
                payment="opaque-x402-proof",
                resource="domainfi.discovery.scan",
                amount_microusd=25000,
                pay_to="0x0000000000000000000000000000000000000000",
            )
        self.assertFalse(receipt["paid"])
        self.assertIn("[REDACTED]", receipt["reason"])
        self.assertNotIn("testtok", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
