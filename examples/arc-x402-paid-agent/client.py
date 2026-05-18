#!/usr/bin/env python3
"""Tiny client for the local Arc x402 paid agent example."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Call the local paid DomainFi discovery endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8765/scan")
    parser.add_argument("--payment", default=None, help="Optional X-Payment header value.")
    args = parser.parse_args()

    headers = {}
    if args.payment:
        headers["X-Payment"] = args.payment
    request = Request(args.url, headers=headers, method="GET")

    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - local demo client
            status = response.status
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8")

    print(f"HTTP {status}")
    try:
        print(json.dumps(json.loads(body), indent=2, sort_keys=True))
    except json.JSONDecodeError:
        print(body)
    return 0 if status in {200, 402} else 1


if __name__ == "__main__":
    raise SystemExit(main())
