#!/usr/bin/env python3
"""Live smoke test for a deployed Arc/Circle Gateway paid-agent endpoint.

This script intentionally does not create payments, hold keys, or submit
transactions. It verifies the deployed seller endpoint contract:

1. A request without X-Payment returns HTTP 402 and an Arc payment intent.
2. If ARC_LIVE_X_PAYMENT is supplied, a paid retry returns HTTP 200 and a
   machine-readable accepted receipt.

Use --expect-402-only for pre-payment deployment checks before you have a live
Gateway/x402 proof.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DEFAULT_SCAN_PATH = "/scan"
EXPECTED_INTENT_KIND = "arc_testnet_payment_intent"


@dataclass(frozen=True)
class SmokeResponse:
    status: int
    json: dict[str, Any]


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _redact(text: str, payment: str | None) -> str:
    if payment:
        text = text.replace(payment, "[REDACTED]")
    gateway_key = _env("CIRCLE_GATEWAY_API_KEY")
    if gateway_key:
        text = text.replace(gateway_key, "[REDACTED]")
    return text


def _build_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("ARC_PAID_AGENT_URL must be an http(s) URL")
    if not path.startswith("/"):
        raise ValueError("scan path must start with /")
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _request_json(url: str, *, payment: str | None, timeout: int) -> SmokeResponse:
    headers = {"Accept": "application/json", "User-Agent": "domainfi-arc-live-smoke/0.1"}
    if payment:
        headers["X-Payment"] = payment
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8")
    except URLError as exc:
        raise RuntimeError(f"request failed: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"endpoint did not return JSON (status={status})") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"endpoint returned non-object JSON (status={status})")
    return SmokeResponse(status=status, json=payload)


def _validate_unpaid(response: SmokeResponse) -> None:
    if response.status != 402:
        raise RuntimeError(f"unpaid request expected HTTP 402, got {response.status}")
    intent = response.json.get("payment_intent")
    if not isinstance(intent, dict):
        raise RuntimeError("402 response is missing payment_intent object")
    if intent.get("kind") != EXPECTED_INTENT_KIND:
        raise RuntimeError(f"payment_intent.kind expected {EXPECTED_INTENT_KIND!r}, got {intent.get('kind')!r}")
    if response.json.get("status") != 402:
        raise RuntimeError("402 response JSON should include status=402")


def _validate_paid(response: SmokeResponse) -> None:
    if response.status != 200:
        reason = response.json.get("payment_rejection") or response.json.get("error") or response.json
        raise RuntimeError(f"paid request expected HTTP 200, got {response.status}: {reason}")
    receipt = response.json.get("payment_receipt")
    if not isinstance(receipt, dict):
        raise RuntimeError("paid response is missing payment_receipt object")
    if receipt.get("paid") is not True:
        raise RuntimeError(f"payment_receipt.paid expected true, got {receipt.get('paid')!r}")
    if not isinstance(response.json.get("opportunities"), list):
        raise RuntimeError("paid response is missing opportunities list")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test a deployed Arc/Circle Gateway paid-agent endpoint.")
    parser.add_argument("--url", default=_env("ARC_PAID_AGENT_URL"), help="Base URL of deployed paid agent, or ARC_PAID_AGENT_URL.")
    parser.add_argument("--path", default=_env("ARC_PAID_AGENT_PATH") or DEFAULT_SCAN_PATH, help="Scan path (default: /scan).")
    parser.add_argument("--payment", default=_env("ARC_LIVE_X_PAYMENT"), help="Opaque live X-Payment proof, or ARC_LIVE_X_PAYMENT.")
    parser.add_argument("--timeout", type=int, default=int(_env("ARC_LIVE_SMOKE_TIMEOUT") or "20"), help="HTTP timeout seconds.")
    parser.add_argument("--expect-402-only", action="store_true", help="Only verify the unpaid 402 challenge; do not require a live payment proof.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.url:
        print("error: --url or ARC_PAID_AGENT_URL is required", file=sys.stderr)
        return 2
    if args.timeout < 1:
        print("error: --timeout must be >= 1", file=sys.stderr)
        return 2
    if not args.expect_402_only and not args.payment:
        print("error: --payment or ARC_LIVE_X_PAYMENT is required unless --expect-402-only is set", file=sys.stderr)
        return 2

    try:
        url = _build_url(args.url, args.path)
        unpaid = _request_json(url, payment=None, timeout=args.timeout)
        _validate_unpaid(unpaid)
        result: dict[str, Any] = {
            "url": url,
            "unpaid_status": unpaid.status,
            "payment_intent": unpaid.json["payment_intent"]["kind"],
        }
        if not args.expect_402_only:
            paid = _request_json(url, payment=args.payment, timeout=args.timeout)
            _validate_paid(paid)
            result.update(
                {
                    "paid_status": paid.status,
                    "payment_receipt": paid.json["payment_receipt"].get("status", "accepted"),
                    "opportunities": len(paid.json.get("opportunities", [])),
                }
            )
    except Exception as exc:  # noqa: BLE001 - CLI smoke prints clean operator error.
        print(f"error: {_redact(str(exc), args.payment)}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
