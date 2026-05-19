#!/usr/bin/env python3
from __future__ import annotations

"""End-to-end smoke test for the local Arc x402 paid-agent demo."""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER = REPO_ROOT / "examples" / "arc-x402-paid-agent" / "server.py"
PAYMENT = "x402-test:domainfi.discovery.scan:25000"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get_json(url: str, *, payment: str | None = None) -> tuple[int, dict]:
    headers = {"Accept": "application/json"}
    if payment:
        headers["X-Payment"] = payment
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _wait_ready(url: str, proc: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 8
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {proc.returncode}")
        try:
            _get_json(url)
            return
        except Exception as exc:  # pragma: no cover - only timing dependent
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"server did not become ready: {last_error}")


def main() -> int:
    port = _free_port()
    url = f"http://127.0.0.1:{port}/scan"
    proc = subprocess.Popen(
        [sys.executable, str(SERVER), "--host", "127.0.0.1", "--port", str(port)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_ready(url, proc)
        unpaid_status, unpaid = _get_json(url)
        paid_status, paid = _get_json(url, payment=PAYMENT)
        if unpaid_status != 402:
            raise RuntimeError(f"expected unpaid HTTP 402, got {unpaid_status}: {unpaid}")
        if paid_status != 200:
            raise RuntimeError(f"expected paid HTTP 200, got {paid_status}: {paid}")
        receipt = paid.get("payment_receipt", {})
        if receipt.get("status") != "accepted":
            raise RuntimeError(f"expected accepted receipt, got {receipt}")
        opportunities = paid.get("opportunities", [])
        if not opportunities:
            raise RuntimeError("expected at least one paid opportunity")
        print(f"url={url}")
        print(f"unpaid_status={unpaid_status}")
        print(f"payment_intent={unpaid.get('payment_intent', {}).get('kind')}")
        print(f"paid_status={paid_status}")
        print(f"payment_receipt={receipt.get('status')}")
        print(f"opportunities={len(opportunities)}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
