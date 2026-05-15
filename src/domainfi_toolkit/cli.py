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
import sys
from pathlib import Path
from typing import Sequence, TextIO

from . import __version__
from .agent import DiscoveryAgent
from .notifiers import ConsoleNotifier
from .providers import MockDomainProvider
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
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of formatted output.",
    )
    p_scan.set_defaults(func=_cmd_scan)

    return parser


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None) -> int:
    out = stdout or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args, out))


def _cmd_version(_args: argparse.Namespace, out: TextIO) -> int:
    print(f"domainfi-agent {__version__}", file=out)
    return 0


def _cmd_scan(args: argparse.Namespace, out: TextIO) -> int:
    try:
        watchlists = []
        for path in args.watchlist:
            watchlists.extend(load_watchlists(path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: failed to load watchlist: {exc}", file=sys.stderr)
        return 2

    if not watchlists:
        print("error: no watchlists loaded", file=sys.stderr)
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
    opportunities = agent.scan(watchlists=watchlists, limit=args.limit)

    if args.json:
        payload = {
            "version": __version__,
            "watchlists": [wl.name for wl in watchlists],
            "count": len(opportunities),
            "opportunities": [opp.to_dict() for opp in opportunities],
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
        return 0

    _print_human_readable(opportunities, watchlists_named=[wl.name for wl in watchlists], out=out)

    notifier = ConsoleNotifier(stream=out)
    alerts = DiscoveryAgent.alerts_for(opportunities[:3])
    if alerts:
        print("", file=out)
        print("Alerts (top 3):", file=out)
        notifier.send(alerts)
    return 0


def _print_human_readable(opportunities, *, watchlists_named, out: TextIO) -> None:
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
