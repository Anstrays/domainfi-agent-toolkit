# Arc x402 paid agent example

A dependency-free local demo of a paid DomainFi discovery endpoint.

This is an **x402-style local demo**, not production wire-compatible x402 verification. It uses a deterministic `X-Payment: x402-test:...` proof so builders can test the payment loop without keys or custody. Replace the verifier with Circle Gateway/x402 verification before production.

Run it on localhost only. Do not bind this demo to a public interface because the local proof is intentionally static.

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
```

The local payment proof is deliberately fake and deterministic. Production wiring should replace it with Circle Gateway/x402 buyer and seller flows.

## Endpoint

- `GET /scan`
- Required payment header: `X-Payment: x402-test:domainfi.discovery.scan:25000`
- Price: `25,000 microUSD` (`$0.025`) in USDC on Arc Testnet

## Why this example matters

It demonstrates the product loop we want on Arc:

- DomainFi signal is a paid API resource.
- Arc/Gateway/x402 handles money movement in USDC.
- The app can price each scan or alert without a subscription wall.
- Doma integration can be swapped in behind the provider interface later.
