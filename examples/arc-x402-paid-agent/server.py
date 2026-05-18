#!/usr/bin/env python3
"""Local paid DomainFi discovery API demo.

This server intentionally uses only the Python standard library and a
local deterministic x402-test proof. It does not hold keys and does not
submit transactions.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domainfi_toolkit.agent import DiscoveryAgent  # noqa: E402
from domainfi_toolkit.arc import (  # noqa: E402
    build_paid_discovery_payload,
    build_payment_required_response,
    estimate_unit_economics,
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
        if not verify_x402_payment_header(payment_header, resource=RESOURCE, amount_microusd=PRICE_MICROUSD):
            self._send_json(
                402,
                build_payment_required_response(
                    resource=RESOURCE,
                    amount_microusd=PRICE_MICROUSD,
                    pay_to=PAY_TO,
                ),
            )
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
        payload["opportunities"] = [opportunity.to_dict() for opportunity in opportunities]
        self._send_json(200, payload)

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
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), PaidDiscoveryHandler)
    print(f"Serving paid DomainFi demo at http://{args.host}:{args.port}/scan")
    print(f"Payment header: X-Payment: x402-test:{RESOURCE}:{PRICE_MICROUSD}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
