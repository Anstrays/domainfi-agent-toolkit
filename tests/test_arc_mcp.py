from __future__ import annotations

import contextlib
import io
import json
import unittest

from domainfi_toolkit.cli import main
from domainfi_toolkit.arc import (
    ARC_TESTNET,
    build_arc_builder_context,
    build_arc_mcp_manifest,
    build_payment_intent,
    verify_payment_intent,
)

PAY_TO = "0x0000000000000000000000000000000000000000"


class ArcMcpManifestTests(unittest.TestCase):
    def test_arc_mcp_manifest_exposes_safe_agent_tools(self) -> None:
        manifest = build_arc_mcp_manifest()

        self.assertEqual(manifest["network"]["chain_id"], ARC_TESTNET.chain_id)
        self.assertEqual(manifest["network"]["native_gas_token"], "USDC")
        tool_names = {tool["name"] for tool in manifest["tools"]}
        self.assertIn("domainfi_arc_payment_intent", tool_names)
        self.assertIn("domainfi_arc_payment_verify", tool_names)
        self.assertIn("domainfi_arc_gateway_verify", tool_names)
        self.assertIn("domainfi_arc_paid_scan", tool_names)
        self.assertIn("domainfi_arc_unit_economics", tool_names)
        self.assertIn("production_replacement_boundary", manifest)
        self.assertIn("Circle Gateway/x402", manifest["production_replacement_boundary"])
        self.assertTrue(manifest["safety"]["testnet_only"])
        self.assertTrue(manifest["safety"]["human_wallet_approval_required"])
        json.loads(json.dumps(manifest))

    def test_arc_builder_context_separates_facts_from_repo_choices_and_unknowns(self) -> None:
        context = build_arc_builder_context()

        self.assertIn("official_arc_facts", context)
        self.assertIn("repo_implementation_choices", context)
        self.assertIn("assumptions_and_unknowns", context)
        self.assertEqual(context["official_arc_facts"]["chain_id"], 5042002)
        self.assertIn("demo-only", " ".join(context["repo_implementation_choices"]).lower())
        self.assertIn("production", " ".join(context["assumptions_and_unknowns"]).lower())


class ArcPaymentIntentTests(unittest.TestCase):
    def test_payment_intent_contains_challenge_proof_and_unit_economics(self) -> None:
        intent = build_payment_intent(
            resource="domainfi.discovery.scan",
            amount_microusd=25_000,
            pay_to=PAY_TO,
            provider_cost_microusd=7_000,
            infra_cost_microusd=2_000,
            settlement_cost_microusd=1_000,
            memo="paid scan for brandable AI domains",
        )

        self.assertEqual(intent["kind"], "arc_testnet_payment_intent")
        self.assertEqual(intent["status"], "requires_payment")
        self.assertEqual(intent["challenge"]["status"], 402)
        self.assertEqual(intent["local_demo_proof"], "x402-test:domainfi.discovery.scan:25000")
        self.assertEqual(intent["unit_economics"]["gross_margin_microusd"], 15_000)
        self.assertEqual(intent["memo"], "paid scan for brandable AI domains")
        self.assertIn("production_verifier", intent)
        json.loads(json.dumps(intent))

    def test_payment_intent_rejects_negative_costs_and_unsafe_memo(self) -> None:
        with self.assertRaises(ValueError):
            build_payment_intent(
                resource="domainfi.discovery.scan",
                amount_microusd=25_000,
                pay_to=PAY_TO,
                provider_cost_microusd=-1,
            )
        with self.assertRaises(ValueError):
            build_payment_intent(
                resource="domainfi.discovery.scan",
                amount_microusd=25_000,
                pay_to=PAY_TO,
                memo="bad\nheader",
            )

    def test_verify_payment_intent_returns_machine_readable_receipt_or_error(self) -> None:
        receipt = verify_payment_intent(
            "x402-test:domainfi.discovery.scan:25000",
            resource="domainfi.discovery.scan",
            amount_microusd=25_000,
        )
        self.assertTrue(receipt["paid"])
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(receipt["network"]["chain_id"], 5042002)
        self.assertIn("local_demo_only", receipt)

        failure = verify_payment_intent(
            "x402-test:domainfi.discovery.scan:1000",
            resource="domainfi.discovery.scan",
            amount_microusd=25_000,
        )
        self.assertFalse(failure["paid"])
        self.assertEqual(failure["status"], "rejected")
        self.assertIn("reason", failure)


class ArcMcpCliTests(unittest.TestCase):
    def test_arc_tools_cli_outputs_manifest_json(self) -> None:
        out = io.StringIO()
        rc = main(["arc-tools", "--json"], stdout=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertIn("tools", payload)
        self.assertEqual(payload["network"]["chain_id"], 5042002)

    def test_arc_intent_cli_outputs_payment_intent_json(self) -> None:
        out = io.StringIO()
        rc = main(
            [
                "arc-intent",
                "--resource",
                "domainfi.discovery.scan",
                "--price-microusd",
                "25000",
                "--pay-to",
                PAY_TO,
                "--json",
            ],
            stdout=out,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "requires_payment")
        self.assertEqual(payload["local_demo_proof"], "x402-test:domainfi.discovery.scan:25000")

    def test_arc_verify_cli_rejects_underpayment_cleanly(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(
                [
                    "arc-verify",
                    "--resource",
                    "domainfi.discovery.scan",
                    "--price-microusd",
                    "25000",
                    "--payment",
                    "x402-test:domainfi.discovery.scan:1000",
                    "--json",
                ],
                stdout=out,
            )
        self.assertEqual(rc, 2)
        self.assertEqual(err.getvalue(), "")
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["paid"])
        self.assertEqual(payload["status"], "rejected")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
