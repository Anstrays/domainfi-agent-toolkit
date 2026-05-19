from __future__ import annotations

"""Minimal dependency-free MCP-style stdio server for Arc paid-agent tools.

This intentionally implements the small JSON-RPC surface needed by coding
agents and local demos without pulling in an MCP SDK dependency. It is safe for
local/testnet use: no private keys, no custody, no production settlement.
"""

import json
import sys
from typing import Any, TextIO

from .agent import DiscoveryAgent
from .arc import (
    build_arc_mcp_manifest,
    build_payment_intent,
    estimate_unit_economics,
    verify_payment_intent,
)
from .providers import MockDomainProvider
from .watchlist import load_watchlists


def _json_text(payload: Any) -> list[dict[str, str]]:
    return [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}]


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": _json_text(payload), "structuredContent": payload}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _list_tools() -> list[dict[str, Any]]:
    tools = []
    for tool in build_arc_mcp_manifest()["tools"]:
        tools.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"],
            }
        )
    return tools


def _paid_scan(arguments: dict[str, Any]) -> dict[str, Any]:
    limit = int(arguments.get("limit", 3))
    if limit < 1 or limit > 50:
        raise ValueError("limit must be in 1..50")
    watchlist_path = arguments.get("watchlist")
    if watchlist_path:
        watchlists = load_watchlists(watchlist_path)
    else:
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        watchlists = load_watchlists(repo_root / "examples" / "watchlists" / "brandable-ai.json")
    opportunities = DiscoveryAgent(provider=MockDomainProvider.default()).scan(watchlists=watchlists, limit=limit)
    return {
        "count": len(opportunities),
        "opportunities": [opportunity.to_dict() for opportunity in opportunities],
    }


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    if name == "domainfi_arc_payment_intent":
        return build_payment_intent(
            resource=str(args.get("resource", "domainfi.discovery.scan")),
            amount_microusd=int(args.get("amount_microusd", args.get("price_microusd", 25_000))),
            pay_to=str(args.get("pay_to", "0x0000000000000000000000000000000000000000")),
            provider_cost_microusd=int(args.get("provider_cost_microusd", 7_000)),
            infra_cost_microusd=int(args.get("infra_cost_microusd", 2_000)),
            settlement_cost_microusd=int(args.get("settlement_cost_microusd", 1_000)),
            memo=args.get("memo"),
        )
    if name == "domainfi_arc_payment_verify":
        return verify_payment_intent(
            args.get("payment"),
            resource=str(args.get("resource", "domainfi.discovery.scan")),
            amount_microusd=int(args.get("amount_microusd", args.get("price_microusd", 25_000))),
        )
    if name == "domainfi_arc_paid_scan":
        return _paid_scan(args)
    if name == "domainfi_arc_unit_economics":
        return estimate_unit_economics(
            provider_cost_microusd=int(args.get("provider_cost_microusd", 7_000)),
            infra_cost_microusd=int(args.get("infra_cost_microusd", 2_000)),
            settlement_cost_microusd=int(args.get("settlement_cost_microusd", 1_000)),
            price_microusd=int(args.get("price_microusd", 25_000)),
        ).to_dict()
    raise ValueError(f"unknown tool: {name}")


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "domainfi-arc-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            }
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _list_tools()}}
        if method == "tools/call":
            name = str(params.get("name", ""))
            arguments = params.get("arguments") or {}
            return {"jsonrpc": "2.0", "id": request_id, "result": _tool_result(call_tool(name, arguments))}
        if method == "notifications/initialized":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        return _error(request_id, -32601, f"unknown method: {method}")
    except (TypeError, ValueError) as exc:
        return _error(request_id, -32602, str(exc))


def serve(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    for line in stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error(None, -32700, f"parse error: {exc}")
        else:
            response = handle_request(request)
        print(json.dumps(response, sort_keys=True), file=stdout, flush=True)
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
