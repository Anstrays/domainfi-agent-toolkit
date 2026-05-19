#!/usr/bin/env python3
"""Local paid DomainFi discovery API demo.

This server intentionally uses only the Python standard library and a
local deterministic x402-test proof. It does not hold keys and does not
submit transactions.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domainfi_toolkit.agent import DiscoveryAgent  # noqa: E402
from domainfi_toolkit.arc import (  # noqa: E402
    CircleGatewayVerifier,
    build_arc_mcp_manifest,
    build_paid_discovery_payload,
    build_payment_intent,
    build_payment_required_response,
    estimate_unit_economics,
    verify_payment_intent,
    verify_x402_payment_header,
)
from domainfi_toolkit.providers import MockDomainProvider  # noqa: E402
from domainfi_toolkit.watchlist import load_watchlists  # noqa: E402

RESOURCE = "domainfi.discovery.scan"
PRICE_MICROUSD = 25_000
PAY_TO = "0x0000000000000000000000000000000000000000"
WATCHLIST_PATH = REPO_ROOT / "examples" / "watchlists" / "brandable-ai.json"


class PaidDiscoveryHandler(BaseHTTPRequestHandler):
    server_version = "DomainFiArcPaidAgent/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler name
        if self.path.split("?", 1)[0] != "/scan":
            self._send_json(404, {"error": "not_found", "expected": "/scan"})
            return

        payment_header = self.headers.get("X-Payment")
        payment_receipt = self._verify_payment(payment_header)
        if not payment_receipt.get("paid"):
            challenge = build_payment_required_response(
                resource=RESOURCE,
                amount_microusd=PRICE_MICROUSD,
                pay_to=PAY_TO,
            )
            challenge["payment_intent"] = build_payment_intent(
                resource=RESOURCE,
                amount_microusd=PRICE_MICROUSD,
                pay_to=PAY_TO,
                memo="paid DomainFi discovery scan",
            )
            challenge["mcp_tools"] = build_arc_mcp_manifest()
            if payment_receipt.get("reason"):
                challenge["payment_rejection"] = payment_receipt
            self._send_json(402, challenge)
            return

        watchlists = load_watchlists(WATCHLIST_PATH)
        opportunities = DiscoveryAgent(provider=MockDomainProvider.default()).scan(watchlists=watchlists, limit=3)
        economics = estimate_unit_economics(
            provider_cost_microusd=7_000,
            infra_cost_microusd=2_000,
            settlement_cost_microusd=1_000,
            price_microusd=PRICE_MICROUSD,
        )
        payload = build_paid_discovery_payload(
            request_id="local-demo",
            watchlist=watchlists[0].name,
            paid=True,
            amount_microusd=PRICE_MICROUSD,
        )
        payload["unit_economics"] = economics.to_dict()
        payload["payment_receipt"] = payment_receipt
        payload["mcp_tools"] = build_arc_mcp_manifest()
        payload["opportunities"] = [opportunity.to_dict() for opportunity in opportunities]
        self._send_json(200, payload)

    def _verify_payment(self, payment_header: str | None) -> dict:
        mode = getattr(self.server, "payment_mode", "local-demo")
        if mode == "gateway":
            verifier = CircleGatewayVerifier(
                getattr(self.server, "gateway_url"),
                api_key=getattr(self.server, "gateway_api_key", None),
                timeout_seconds=getattr(self.server, "gateway_timeout", 20),
            )
            return verifier.verify(
                payment=payment_header or "",
                resource=RESOURCE,
                amount_microusd=PRICE_MICROUSD,
                pay_to=PAY_TO,
            )
        if not verify_x402_payment_header(payment_header, resource=RESOURCE, amount_microusd=PRICE_MICROUSD):
            return {"paid": False, "status": "rejected", "reason": "missing_or_invalid_local_demo_proof"}
        return verify_payment_intent(payment_header, resource=RESOURCE, amount_microusd=PRICE_MICROUSD)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        print(f"[paid-agent] {self.address_string()} - {format % args}", file=sys.stderr)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Arc x402 paid DomainFi agent demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--payment-mode",
        choices=("local-demo", "gateway"),
        default=os.environ.get("DOMAINFI_PAYMENT_MODE", "local-demo"),
        help="Payment verifier: local deterministic demo proof or Circle Gateway verifier.",
    )
    parser.add_argument("--gateway-url", default=os.environ.get("CIRCLE_GATEWAY_URL"))
    parser.add_argument("--gateway-api-key", default=os.environ.get("CIRCLE_GATEWAY_API_KEY"))
    parser.add_argument("--gateway-timeout", type=int, default=int(os.environ.get("CIRCLE_GATEWAY_TIMEOUT", "20")))
    args = parser.parse_args()

    if args.payment_mode == "gateway" and not args.gateway_url:
        parser.error("--gateway-url or CIRCLE_GATEWAY_URL is required when --payment-mode gateway")
    if args.gateway_timeout < 1:
        parser.error("--gateway-timeout must be >= 1")

    httpd = ThreadingHTTPServer((args.host, args.port), PaidDiscoveryHandler)
    setattr(httpd, "payment_mode", args.payment_mode)
    setattr(httpd, "gateway_url", args.gateway_url)
    setattr(httpd, "gateway_api_key", args.gateway_api_key)
    setattr(httpd, "gateway_timeout", args.gateway_timeout)
    print(f"Serving paid DomainFi demo at http://{args.host}:{args.port}/scan")
    print(f"Payment mode: {args.payment_mode}")
    if args.payment_mode == "local-demo":
        print(f"Payment header: X-Payment: x402-test:{RESOURCE}:{PRICE_MICROUSD}")
    else:
        print("Payment header: X-Payment: <opaque Circle Gateway/x402 proof>")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
