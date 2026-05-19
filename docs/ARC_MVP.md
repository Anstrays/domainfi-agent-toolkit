# Arc MVP: paid DomainFi discovery agent

This MVP turns the existing DomainFi discovery prototype into a Circle/Arc-native product wedge: a paid agent endpoint for domain intelligence signals.

## What we are building

A builder can clone this repo and run a local pay-per-request DomainFi discovery API:

1. A buyer agent requests a domain scan or watchlist signal.
2. The server returns HTTP `402 Payment Required` with an x402-style USDC price.
3. The buyer retries with an `X-Payment` proof.
4. The server returns the discovery payload and unit-economics context.
5. In production, the local `x402-test` proof is replaced with Circle Gateway/x402 verification and Arc settlement.

The point is not custody or trading automation. The point is monetized intelligence: paid scans, paid alerts, and paid API calls for Doma/domain opportunities.

## Why Arc

Arc is a strong fit because:

- **USDC is the native gas token**: users and agents can reason about scan price, settlement, and gas in dollars.
- **Sub-second deterministic finality**: fits alert loops and pay-per-signal APIs where agents should not wait for many confirmations.
- **EVM compatibility**: builders can keep standard Python/HTTP agent code and later add Solidity/Viem/Foundry pieces.
- **Circle Gateway/x402 path**: lets the project sell micro-priced API calls before building subscriptions, dashboards, and billing.

## Arc Testnet constants

- Network: Arc Testnet
- Chain ID: `5042002`
- RPC: `https://rpc.testnet.arc.network`
- Explorer: `https://testnet.arcscan.app`
- Faucet: `https://faucet.circle.com`
- Native gas token: `USDC`

## Local runbook

From the repo root:

```bash
# Show Arc config, x402 challenge shape, and unit economics
PYTHONPATH=src python3 -m domainfi_toolkit arc-mvp --json

# Start the paid endpoint demo
PYTHONPATH=src python3 examples/arc-x402-paid-agent/server.py --port 8765

# In another terminal, call without payment: expect HTTP 402 JSON
python3 examples/arc-x402-paid-agent/client.py --url http://127.0.0.1:8765/scan

# Call with local demo payment proof: expect HTTP 200 JSON
python3 examples/arc-x402-paid-agent/client.py \
  --url http://127.0.0.1:8765/scan \
  --payment 'x402-test:domainfi.discovery.scan:25000'
```

No private keys or production Circle credentials are required for the local MVP.

## MCP-style agent tools

The Arc layer now exposes a dependency-free manifest and a minimal JSON-RPC/MCP-style stdio server that coding agents and future MCP deployments can reuse without importing web3 libraries:

```bash
# Tool names, JSON schemas, safety flags, and production boundary
PYTHONPATH=src python3 -m domainfi_toolkit arc-tools --json

# Build a payment intent for a paid resource
PYTHONPATH=src python3 -m domainfi_toolkit arc-intent \
  --resource domainfi.discovery.scan \
  --price-microusd 25000 \
  --pay-to 0x0000000000000000000000000000000000000000 \
  --json

# Verify a local demo proof and return a receipt/rejection
PYTHONPATH=src python3 -m domainfi_toolkit arc-verify \
  --resource domainfi.discovery.scan \
  --price-microusd 25000 \
  --payment 'x402-test:domainfi.discovery.scan:25000' \
  --json

# List tools through the stdio JSON-RPC/MCP-style server
printf '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n' | \
  PYTHONPATH=src python3 -m domainfi_toolkit.arc_mcp

# End-to-end smoke test the local HTTP paid-agent loop
python3 scripts/smoke_arc_paid_agent.py
```

The manifest currently describes four safe tools:

- `domainfi_arc_payment_intent`: build an Arc Testnet payment intent and 402 challenge.
- `domainfi_arc_payment_verify`: verify the local demo proof and return a receipt shape.
- `domainfi_arc_paid_scan`: run the paid DomainFi scan after verification succeeds.
- `domainfi_arc_unit_economics`: calculate microUSD cost, price, and margin.

The reusable coding-agent prompt is in [`prompts/wire-arc-testnet-status.md`](../prompts/wire-arc-testnet-status.md). It forces source grounding, explicit assumptions, TDD, and the Circle Gateway/x402 production replacement boundary.

Important: this is an **x402-style local demo**, not production wire-compatible x402 verification. The deterministic `x402-test:*` proof exists only so the HTTP 402 -> paid retry loop can run without keys. Run the example on localhost only; do not expose it publicly until `verify_x402_payment_header(...)` is replaced with Circle Gateway/x402 verification.

## Production wiring path

Replace only the payment verification boundary:

- Seller side: replace `verify_x402_payment_header(...)` with Circle Gateway/x402 seller verification.
- Buyer side: replace the `x402-test:*` header with a real Gateway/x402 payment flow.
- Settlement: use Arc Testnet and Circle docs for wallet funding, Gateway unified balance, and USDC movement.
- Data: replace `MockDomainProvider` with Doma API/SDK provider when endpoints are available.

## Unit economics thesis

Default demo price: `25,000 microUSD` = `$0.025` per scan.

Default estimated costs:

- Provider/model/data cost: `7,000 microUSD`
- Infra cost: `2,000 microUSD`
- Settlement/accounting cost: `1,000 microUSD`
- Total cost: `10,000 microUSD`
- Gross margin: `15,000 microUSD` = `60%`

This is intentionally small enough for agent-to-agent calls but large enough to model a real business:

- $0.005-$0.025: lightweight watchlist match or cached signal
- $0.025-$0.10: fresh ranked scan with explanations
- $0.10-$1.00+: high-intent portfolio/expiry/risk report or webhook bundle

## Demand thesis

There is likely demand if the product is positioned as paid domain intelligence, not generic “AI + crypto”:

- Domain investors already pay for discovery, appraisal, expiry, and marketplace data.
- Doma/DomainFi turns domains into programmable assets, increasing the need for monitoring and automation.
- Agents need low-friction paid APIs; x402/Gateway makes “pay for one signal” possible without SaaS onboarding.
- Arc gives a clean Circle-native story: USDC pricing, USDC gas, fast settlement, and enterprise-friendly stablecoin rails.

The first buyers are not mass consumers. They are:

1. Doma ecosystem builders who need demo agents/templates.
2. Domain traders/investors who want filtered watchlist alerts.
3. AI-agent builders looking for a concrete paid API example.
4. Crypto teams that want a practical Arc/Gateway/x402 showcase.

## MVP success criteria

- A developer can run the local paid endpoint in under five minutes.
- The repo documents Arc constants and why USDC-native gas matters.
- The API exposes a clear HTTP 402 -> paid retry -> JSON result loop.
- Unit economics are visible per request.
- The code avoids custody, private keys, and automated transactions until production payment verification is explicitly added.
