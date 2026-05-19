# Arc x402 paid agent example

A dependency-free local demo of a paid DomainFi discovery endpoint.

This is an **x402-style local demo by default**, not production wire-compatible x402 verification. It uses a deterministic `X-Payment: x402-test:...` proof so builders can test the payment loop without keys or custody. For production-style verification, run `--payment-mode gateway` with `CIRCLE_GATEWAY_URL` and `CIRCLE_GATEWAY_API_KEY` supplied through deployment secrets.

Run the local-demo mode on localhost only. Do not bind that mode to a public interface because the local proof is intentionally static.

## Run

```bash
# From repo root
PYTHONPATH=src python3 examples/arc-x402-paid-agent/server.py --port 8765

# Request without payment: returns HTTP 402 and payment instructions
python3 examples/arc-x402-paid-agent/client.py --url http://127.0.0.1:8765/scan

# Request with local demo payment proof: returns HTTP 200
python3 examples/arc-x402-paid-agent/client.py \
  --url http://127.0.0.1:8765/scan \
  --payment 'x402-test:domainfi.discovery.scan:25000'

# Optional production-style verifier seam: Circle Gateway/x402 verification
DOMAINFI_PAYMENT_MODE=gateway \
CIRCLE_GATEWAY_URL=https://gateway.example.test/v1 \
CIRCLE_GATEWAY_API_KEY=redacted \
PYTHONPATH=src python3 examples/arc-x402-paid-agent/server.py --port 8765
```

The local payment proof is deliberately fake and deterministic. Production wiring should replace it with Circle Gateway/x402 buyer and seller flows.

## Endpoint

- `GET /scan`
- Required payment header: `X-Payment: x402-test:domainfi.discovery.scan:25000`
- Price: `25,000 microUSD` (`$0.025`) in USDC on Arc Testnet
- Unpaid response includes a `payment_intent` and `mcp_tools` manifest so agent clients can discover the payment/verification flow.
- Paid response includes `payment_receipt`, `unit_economics`, and the paid opportunities payload.

## CLI helpers

```bash
# MCP-style tool manifest
PYTHONPATH=src python3 -m domainfi_toolkit arc-tools --json

# Payment intent / receipt helpers
PYTHONPATH=src python3 -m domainfi_toolkit arc-intent --json
PYTHONPATH=src python3 -m domainfi_toolkit arc-verify \
  --payment 'x402-test:domainfi.discovery.scan:25000' \
  --json
CIRCLE_GATEWAY_URL=https://gateway.example.test/v1 \
CIRCLE_GATEWAY_API_KEY=redacted \
PYTHONPATH=src python3 -m domainfi_toolkit arc-gateway-verify \
  --payment '<opaque-x402-proof>' \
  --json

# JSON-RPC/MCP-style stdio server
printf '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n' | \
  PYTHONPATH=src python3 -m domainfi_toolkit.arc_mcp

# Full local HTTP smoke test
python3 scripts/smoke_arc_paid_agent.py

# Production deployment checklist and live smoke runbook
python3 scripts/live_arc_gateway_smoke.py --help
```

For deployment, copy `.env.example` into your platform's secret/env UI and follow [`docs/ARC_PRODUCTION_DEPLOYMENT.md`](../../docs/ARC_PRODUCTION_DEPLOYMENT.md). Use `scripts/live_arc_gateway_smoke.py --expect-402-only` for a post-deploy challenge check, then rerun it with `ARC_LIVE_X_PAYMENT` after a real buyer/Gateway proof is available.

## Why this example matters

It demonstrates the product loop we want on Arc:

- DomainFi signal is a paid API resource.
- Arc/Gateway/x402 handles money movement in USDC.
- The app can price each scan or alert without a subscription wall.
