"""Command-line entry point for the prototype agent.

The CLI is intentionally small and dependency-free. It exists to
prove that the pipeline works end-to-end and to give grant reviewers
something concrete to run.

Examples:

    python -m domainfi_toolkit version
    python -m domainfi_toolkit scan --watchlist examples/watchlists/brandable-ai.json
    python -m domainfi_toolkit scan --watchlist <path> --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Sequence, TextIO

from . import __version__
from .agent import DiscoveryAgent
from .arc import (
    CircleGatewayVerifier,
    ARC_TESTNET,
    build_arc_mcp_manifest,
    build_payment_intent,
    build_payment_required_response,
    estimate_unit_economics,
    verify_payment_intent,
)
from .notifiers import ConsoleNotifier
from .providers import MockDomainProvider
from .scoring import explain as explain_score, load_weights, reset_weights
from .watchlist import load_watchlists


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="domainfi-agent",
        description="DomainFi Agent Toolkit prototype CLI.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="Print the package version.")
    p_version.set_defaults(func=_cmd_version)

    p_scan = sub.add_parser("scan", help="Scan inventory for watchlist matches.")
    p_scan.add_argument(
        "--watchlist",
        action="append",
        required=True,
        type=Path,
        help="Path to a watchlist JSON file. May be passed multiple times.",
    )
    p_scan.add_argument(
        "--inventory",
        type=Path,
        default=None,
        help="Optional custom inventory JSON. Defaults to the bundled mock data.",
    )
    p_scan.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of opportunities to return (default: 10).",
    )
    p_scan.add_argument(
        "--sort-by",
        choices=("score", "price", "name"),
        default="score",
        help="Sort opportunities by score, price, or domain name (default: score).",
    )
    p_scan.add_argument(
        "--min-score",
        type=int,
        default=None,
        help="Override watchlist min_score for this run.",
    )
    p_scan.add_argument(
        "--weights",
        type=Path,
        default=None,
        help="Optional scoring weights JSON file. Keys must sum to 100.",
    )
    p_scan.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON payload to a file. Human output still goes to stdout unless --json is set.",
    )
    p_scan.add_argument(
        "--explain",
        action="store_true",
        help="Print compact per-domain scoring explanations in human output.",
    )
    p_scan.add_argument(
        "--no-color",
        action="store_true",
        help="Accepted for CI/log compatibility; output is plain text by default.",
    )
    p_scan.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of formatted output.",
    )
    p_scan.set_defaults(func=_cmd_scan)

    p_arc = sub.add_parser("arc-mvp", help="Print Arc paid-agent MVP config and unit economics.")
    p_arc.add_argument(
        "--resource",
        default="domainfi.discovery.scan",
        help="Paid API resource name (default: domainfi.discovery.scan).",
    )
    p_arc.add_argument(
        "--price-microusd",
        type=int,
        default=25_000,
        help="Price per request in microUSD (default: 25000 = $0.025).",
    )
    p_arc.add_argument(
        "--provider-cost-microusd",
        type=int,
        default=7_000,
        help="Estimated provider/model cost per request in microUSD.",
    )
    p_arc.add_argument(
        "--infra-cost-microusd",
        type=int,
        default=2_000,
        help="Estimated infra cost per request in microUSD.",
    )
    p_arc.add_argument(
        "--settlement-cost-microusd",
        type=int,
        default=1_000,
        help="Estimated settlement/accounting cost per request in microUSD.",
    )
    p_arc.add_argument(
        "--pay-to",
        default="0x0000000000000000000000000000000000000000",
        help="Demo seller address for the x402 challenge.",
    )
    p_arc.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_arc.set_defaults(func=_cmd_arc_mvp)

    p_arc_tools = sub.add_parser("arc-tools", help="Print MCP-style Arc paid-agent tool manifest.")
    p_arc_tools.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_arc_tools.set_defaults(func=_cmd_arc_tools)

    p_arc_intent = sub.add_parser("arc-intent", help="Build an Arc x402-style payment intent.")
    _add_arc_payment_args(p_arc_intent)
    p_arc_intent.add_argument("--memo", default=None, help="Optional safe memo for the intent.")
    p_arc_intent.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_arc_intent.set_defaults(func=_cmd_arc_intent)

    p_arc_verify = sub.add_parser("arc-verify", help="Verify a local Arc x402-test payment proof.")
    p_arc_verify.add_argument("--resource", default="domainfi.discovery.scan")
    p_arc_verify.add_argument("--price-microusd", type=int, default=25_000)
    p_arc_verify.add_argument("--payment", required=True, help="X-Payment header value to verify.")
    p_arc_verify.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_arc_verify.set_defaults(func=_cmd_arc_verify)

    p_arc_gateway = sub.add_parser(
        "arc-gateway-verify",
        help="Verify an opaque x402 proof with a configured Circle Gateway verifier.",
    )
    p_arc_gateway.add_argument("--resource", default="domainfi.discovery.scan")
    p_arc_gateway.add_argument("--price-microusd", type=int, default=25_000)
    p_arc_gateway.add_argument(
        "--pay-to",
        default="0x0000000000000000000000000000000000000000",
        help="Seller address expected by the verifier.",
    )
    p_arc_gateway.add_argument("--payment", required=True, help="Opaque X-Payment proof to verify.")
    p_arc_gateway.add_argument(
        "--gateway-url",
        default=os.environ.get("CIRCLE_GATEWAY_URL"),
        help="Circle Gateway/x402 verifier base URL (or CIRCLE_GATEWAY_URL).",
    )
    p_arc_gateway.add_argument(
        "--gateway-api-key",
        default=os.environ.get("CIRCLE_GATEWAY_API_KEY"),
        help="Verifier bearer token (or CIRCLE_GATEWAY_API_KEY).",
    )
    p_arc_gateway.add_argument(
        "--gateway-timeout",
        type=int,
        default=int(os.environ.get("CIRCLE_GATEWAY_TIMEOUT", "20")),
        help="Gateway verifier timeout in seconds (default: 20).",
    )
    p_arc_gateway.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_arc_gateway.set_defaults(func=_cmd_arc_gateway_verify)

    return parser


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None) -> int:
    out = stdout or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args, out))


def _cmd_version(_args: argparse.Namespace, out: TextIO) -> int:
    print(f"domainfi-agent {__version__}", file=out)
    return 0


def _add_arc_payment_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--resource", default="domainfi.discovery.scan")
    parser.add_argument(
        "--price-microusd",
        type=int,
        default=25_000,
        help="Price per request in microUSD (default: 25000 = $0.025).",
    )
    parser.add_argument(
        "--provider-cost-microusd",
        type=int,
        default=7_000,
        help="Estimated provider/model cost per request in microUSD.",
    )
    parser.add_argument(
        "--infra-cost-microusd",
        type=int,
        default=2_000,
        help="Estimated infra cost per request in microUSD.",
    )
    parser.add_argument(
        "--settlement-cost-microusd",
        type=int,
        default=1_000,
        help="Estimated settlement/accounting cost per request in microUSD.",
    )
    parser.add_argument(
        "--pay-to",
        default="0x0000000000000000000000000000000000000000",
        help="Demo seller address for the x402 challenge.",
    )


def _cmd_arc_tools(args: argparse.Namespace, out: TextIO) -> int:
    manifest = build_arc_mcp_manifest()
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True), file=out)
        return 0
    print("Arc paid-agent MCP tools", file=out)
    print(f"Network: {manifest['network']['name']} chain_id={manifest['network']['chain_id']}", file=out)
    for tool in manifest["tools"]:
        print(f"- {tool['name']}: {tool['description']}", file=out)
    print(f"Boundary: {manifest['production_replacement_boundary']}", file=out)
    return 0


def _cmd_arc_intent(args: argparse.Namespace, out: TextIO) -> int:
    try:
        intent = build_payment_intent(
            resource=args.resource,
            amount_microusd=args.price_microusd,
            pay_to=args.pay_to,
            provider_cost_microusd=args.provider_cost_microusd,
            infra_cost_microusd=args.infra_cost_microusd,
            settlement_cost_microusd=args.settlement_cost_microusd,
            memo=args.memo,
        )
    except (TypeError, ValueError) as exc:
        print(f"error: invalid Arc payment intent parameters: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(intent, indent=2, sort_keys=True), file=out)
        return 0
    print("Arc payment intent", file=out)
    print(f"Resource: {args.resource}", file=out)
    print(f"Price: {args.price_microusd} microUSD", file=out)
    print(f"Payment header demo: X-Payment: {intent['local_demo_proof']}", file=out)
    return 0


def _cmd_arc_verify(args: argparse.Namespace, out: TextIO) -> int:
    try:
        receipt = verify_payment_intent(
            args.payment,
            resource=args.resource,
            amount_microusd=args.price_microusd,
        )
    except (TypeError, ValueError) as exc:
        print(f"error: invalid Arc payment verification parameters: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True), file=out)
    else:
        status = "accepted" if receipt["paid"] else f"rejected: {receipt.get('reason', 'unknown')}"
        print(f"Arc payment verification {status}", file=out)
    return 0 if receipt["paid"] else 2


def _cmd_arc_gateway_verify(args: argparse.Namespace, out: TextIO) -> int:
    if not args.gateway_url:
        print("error: --gateway-url or CIRCLE_GATEWAY_URL is required", file=sys.stderr)
        return 2
    if args.gateway_timeout < 1:
        print("error: --gateway-timeout must be >= 1", file=sys.stderr)
        return 2
    try:
        verifier = CircleGatewayVerifier(
            args.gateway_url,
            api_key=args.gateway_api_key,
            timeout_seconds=args.gateway_timeout,
        )
        receipt = verifier.verify(
            payment=args.payment,
            resource=args.resource,
            amount_microusd=args.price_microusd,
            pay_to=args.pay_to,
        )
    except (TypeError, ValueError) as exc:
        print(f"error: invalid Arc Gateway verification parameters: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True), file=out)
    else:
        status = "accepted" if receipt.get("paid") else f"rejected: {receipt.get('reason', 'unknown')}"
        print(f"Arc Gateway verification {status}", file=out)
    return 0 if receipt.get("paid") else 2


def _cmd_arc_mvp(args: argparse.Namespace, out: TextIO) -> int:
    try:
        economics = estimate_unit_economics(
            provider_cost_microusd=args.provider_cost_microusd,
            infra_cost_microusd=args.infra_cost_microusd,
            settlement_cost_microusd=args.settlement_cost_microusd,
            price_microusd=args.price_microusd,
        )
        challenge = build_payment_required_response(
            resource=args.resource,
            amount_microusd=args.price_microusd,
            pay_to=args.pay_to,
        )
    except (TypeError, ValueError) as exc:
        print(f"error: invalid Arc MVP parameters: {exc}", file=sys.stderr)
        return 2

    payload = {
        "version": __version__,
        "arc": ARC_TESTNET.to_dict(),
        "x402_challenge": challenge,
        "unit_economics": economics.to_dict(),
        "demand_thesis": [
            "Domain intelligence is naturally pay-per-signal: users pay for filtered opportunities, not raw listings.",
            "Arc makes costs legible because gas and API settlement can both be denominated in USDC.",
            "x402/Gateway lets the project sell scans, alerts, and API calls before building a full SaaS subscription stack.",
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
        return 0

    print("Arc MVP: paid DomainFi discovery agent", file=out)
    print(f"Network: {ARC_TESTNET.name} chain_id={ARC_TESTNET.chain_id} gas={ARC_TESTNET.native_gas_token}", file=out)
    print(f"RPC: {ARC_TESTNET.rpc_url}", file=out)
    print(f"Resource: {args.resource}", file=out)
    print(f"Price: {args.price_microusd} microUSD per request", file=out)
    print(
        "Gross margin: "
        f"{economics.gross_margin_microusd} microUSD ({economics.gross_margin_percent}%)",
        file=out,
    )
    print(f"Payment header demo: X-Payment: x402-test:{args.resource}:{args.price_microusd}", file=out)
    return 0


def _cmd_scan(args: argparse.Namespace, out: TextIO) -> int:
    if args.limit < 1:
        print("error: --limit must be >= 1", file=sys.stderr)
        return 2
    if args.min_score is not None and not 0 <= args.min_score <= 100:
        print("error: --min-score must be in 0..100", file=sys.stderr)
        return 2
    try:
        watchlists = []
        for path in args.watchlist:
            watchlists.extend(load_watchlists(path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: failed to load watchlist: {exc}", file=sys.stderr)
        return 2
    if args.min_score is not None:
        watchlists = [replace(watchlist, min_score=args.min_score) for watchlist in watchlists]

    if not watchlists:
        print("error: no watchlists loaded", file=sys.stderr)
        return 2

    # Always start from defaults so repeated CLI calls in one process cannot
    # accidentally inherit custom weights from a prior run.
    reset_weights()
    if args.weights:
        try:
            load_weights(args.weights)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"error: failed to load weights: {exc}", file=sys.stderr)
            return 2

    if args.inventory:
        try:
            provider = MockDomainProvider.from_json_file(args.inventory)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: failed to load inventory: {exc}", file=sys.stderr)
            return 2
    else:
        provider = MockDomainProvider.default()

    agent = DiscoveryAgent(provider=provider)
    opportunities = agent.scan(watchlists=watchlists)
    if args.min_score is not None:
        opportunities = [opp for opp in opportunities if opp.score.score >= args.min_score]
    opportunities = _sort_opportunities(opportunities, args.sort_by)[: args.limit]

    payload = {
        "version": __version__,
        "watchlists": [wl.name for wl in watchlists],
        "count": len(opportunities),
        "opportunities": [opp.to_dict() for opp in opportunities],
    }
    if args.output:
        try:
            args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"error: failed to write output: {exc}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
        return 0

    _print_human_readable(
        opportunities,
        watchlists_named=[wl.name for wl in watchlists],
        out=out,
        explain=args.explain,
    )

    notifier = ConsoleNotifier(stream=out)
    alerts = DiscoveryAgent.alerts_for(opportunities[:3])
    if alerts:
        print("", file=out)
        print("Alerts (top 3):", file=out)
        notifier.send(alerts)
    return 0


def _sort_opportunities(opportunities, sort_by: str):
    if sort_by == "price":
        return sorted(
            opportunities,
            key=lambda opp: (float("inf") if opp.listing is None else opp.listing.price_usd, opp.domain.name),
        )
    if sort_by == "name":
        return sorted(opportunities, key=lambda opp: opp.domain.name)
    return sorted(opportunities, key=lambda opp: opp.score.score, reverse=True)


def _print_human_readable(opportunities, *, watchlists_named, out: TextIO, explain: bool = False) -> None:
    print(f"Watchlists scanned: {', '.join(watchlists_named)}", file=out)
    print(f"Found {len(opportunities)} domain opportunities", file=out)
    if not opportunities:
        return
    print("", file=out)
    for index, opp in enumerate(opportunities, start=1):
        listing = opp.listing
        price = f"${listing.price_usd:.0f} on {listing.marketplace}" if listing else "no active listing"
        print(f"#{index:02d}  {opp.domain.name}  score={opp.score.score}/100  ({price})", file=out)
        print(f"      watchlist: {opp.matched_watchlist}", file=out)
        for signal in opp.score.signals:
            if signal.contribution:
                print(f"      + {signal.name:<13} {signal.contribution:>3}  {signal.explanation}", file=out)
        if explain:
            print(f"      explain: {explain_score(opp.score)}", file=out)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
