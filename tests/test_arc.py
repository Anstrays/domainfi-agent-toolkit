from __future__ import annotations

import json
import unittest

from domainfi_toolkit.arc import (
    ARC_TESTNET,
    UnitEconomics,
    build_payment_required_response,
    build_paid_discovery_payload,
    estimate_unit_economics,
    parse_x402_payment_header,
    verify_x402_payment_header,
)


class ArcConfigTests(unittest.TestCase):
    def test_arc_testnet_constants_are_documented(self) -> None:
        self.assertEqual(ARC_TESTNET.chain_id, 5042002)
        self.assertEqual(ARC_TESTNET.native_gas_token, "USDC")
        self.assertTrue(ARC_TESTNET.rpc_url.startswith("https://"))
        self.assertIn("arcscan", ARC_TESTNET.explorer_url)


class X402PaymentTests(unittest.TestCase):
    def test_payment_required_response_is_machine_readable(self) -> None:
        payload = build_payment_required_response(
            resource="domainfi.discovery.scan",
            amount_microusd=25_000,
            pay_to="0x0000000000000000000000000000000000000000",
        )

        self.assertEqual(payload["status"], 402)
        self.assertEqual(payload["accepts"][0]["asset"], "USDC")
        self.assertEqual(payload["accepts"][0]["network"], "arc-testnet")
        self.assertEqual(payload["accepts"][0]["amount_microusd"], 25_000)
        self.assertIn("X-Payment", payload["instructions"])

        # The response should be safe to return from a tiny HTTP server.
        json.loads(json.dumps(payload))

    def test_x402_header_parser_and_verifier(self) -> None:
        header = "x402-test:domainfi.discovery.scan:25000"
        parsed = parse_x402_payment_header(header)
        self.assertEqual(parsed.resource, "domainfi.discovery.scan")
        self.assertEqual(parsed.amount_microusd, 25_000)
        self.assertTrue(
            verify_x402_payment_header(
                header,
                resource="domainfi.discovery.scan",
                amount_microusd=25_000,
            )
        )
        self.assertFalse(
            verify_x402_payment_header(
                header,
                resource="domainfi.discovery.scan",
                amount_microusd=30_000,
            )
        )

    def test_malformed_x402_header_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_x402_payment_header("Bearer token")
        with self.assertRaises(ValueError):
            parse_x402_payment_header("x402-test:domainfi.discovery.scan:not-a-number")

    def test_zero_amount_paid_resource_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_payment_required_response(
                resource="domainfi.discovery.scan",
                amount_microusd=0,
                pay_to="0x0000000000000000000000000000000000000000",
            )
        with self.assertRaises(ValueError):
            parse_x402_payment_header("x402-test:domainfi.discovery.scan:0")

    def test_payment_required_response_rejects_unsafe_resource_and_pay_to(self) -> None:
        with self.assertRaises(ValueError):
            build_payment_required_response(
                resource="domainfi:discovery:scan",
                amount_microusd=25_000,
                pay_to="0x0000000000000000000000000000000000000000",
            )
        with self.assertRaises(ValueError):
            build_payment_required_response(
                resource="domainfi.discovery.scan",
                amount_microusd=25_000,
                pay_to="not-an-address",
            )


class UnitEconomicsTests(unittest.TestCase):
    def test_unit_economics_estimate_has_margin(self) -> None:
        economics = estimate_unit_economics(
            provider_cost_microusd=7_000,
            infra_cost_microusd=2_000,
            settlement_cost_microusd=1_000,
            price_microusd=25_000,
        )
        self.assertIsInstance(economics, UnitEconomics)
        self.assertEqual(economics.total_cost_microusd, 10_000)
        self.assertEqual(economics.gross_margin_microusd, 15_000)
        self.assertAlmostEqual(economics.gross_margin_percent, 60.0)

    def test_paid_discovery_payload_contains_arc_and_payment_context(self) -> None:
        payload = build_paid_discovery_payload(
            request_id="demo-1",
            watchlist="brandable-ai",
            paid=True,
            amount_microusd=25_000,
        )
        self.assertEqual(payload["request_id"], "demo-1")
        self.assertEqual(payload["payment"]["network"], "arc-testnet")
        self.assertEqual(payload["payment"]["asset"], "USDC")
        self.assertEqual(payload["payment"]["paid"], True)
        self.assertEqual(payload["watchlist"], "brandable-ai")
        self.assertIn("why_arc", payload)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
