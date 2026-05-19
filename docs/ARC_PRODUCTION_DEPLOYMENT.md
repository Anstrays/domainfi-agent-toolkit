# Arc Production Deployment

This runbook is only for the Arc/Circle/x402 paid-agent path.

The repository remains secret-free: production values belong in the deployment platform's secret/env store, never in git.

## Production deployment checklist

### 1. Preflight

- Confirm the branch is current and green:
  - `python3 scripts/validate_repo.py`
  - `PYTHONPATH=src python3 -m unittest -q`
  - `python3 scripts/smoke_arc_paid_agent.py`
- Confirm the endpoint you are deploying is `examples/arc-x402-paid-agent/server.py`.
- Confirm Arc assumptions are testnet-only unless the official Arc/Circle docs say otherwise:
  - Arc Testnet chain ID: `5042002`
  - Arc gas token: USDC
  - local demo proof: `x402-test:*` only, never production settlement

### 2. Configure deployment env

Use [`examples/arc-x402-paid-agent/.env.example`](../examples/arc-x402-paid-agent/.env.example) as the template.

Required for Gateway mode:

```bash
DOMAINFI_PAYMENT_MODE=gateway
CIRCLE_GATEWAY_URL=https://gateway.example.test/v1
CIRCLE_GATEWAY_API_KEY=redacted
CIRCLE_GATEWAY_TIMEOUT=20
```

Required for a post-deploy live smoke:

```bash
ARC_PAID_AGENT_URL=https://paid-agent.example.test
ARC_PAID_AGENT_PATH=/scan
ARC_LIVE_X_PAYMENT=redacted
ARC_LIVE_SMOKE_TIMEOUT=20
```

`ARC_LIVE_X_PAYMENT` must come from a real buyer/Gateway x402 flow. Do not paste it into docs, PRs, logs, or screenshots.

### 3. Deploy command

The server is dependency-free and can run anywhere with Python 3.10+.

Generic command:

```bash
PYTHONPATH=src python3 examples/arc-x402-paid-agent/server.py \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8765}" \
  --payment-mode gateway
```

Platform notes:

- **VPS/systemd**: set env in an EnvironmentFile outside the repo and bind behind TLS reverse proxy.
- **Render/Railway/Fly.io**: set env through the provider UI; use the generic command as the start command.
- **Local staging**: use `--host 127.0.0.1` and never expose local-demo mode publicly.

### 4. Safety gates before public traffic

- TLS is enabled at the public URL.
- `DOMAINFI_PAYMENT_MODE=gateway` is set in the public deployment.
- `CIRCLE_GATEWAY_URL` is the intended verifier endpoint.
- The deployment does not print `CIRCLE_GATEWAY_API_KEY` or `ARC_LIVE_X_PAYMENT`.
- A no-payment request returns HTTP `402` with `payment_intent.kind = arc_testnet_payment_intent`.
- A paid request with a live proof returns HTTP `200` and `payment_receipt.paid = true`.
- Logs are retained long enough to debug failed verification, but do not store proof values beyond normal request metadata.
- Rate limiting is configured at the edge if the endpoint is public.

## Live smoke test

### 402-only pre-payment check

Run this immediately after deploy, before you have a live buyer proof:

```bash
ARC_PAID_AGENT_URL=https://paid-agent.example.test \
python3 scripts/live_arc_gateway_smoke.py --expect-402-only
```

Expected output includes:

```json
{
  "payment_intent": "arc_testnet_payment_intent",
  "unpaid_status": 402
}
```

### Full paid live smoke

Run this only after a real buyer/Gateway flow creates an opaque x402 proof:

```bash
ARC_PAID_AGENT_URL=https://paid-agent.example.test \
ARC_LIVE_X_PAYMENT=redacted \
python3 scripts/live_arc_gateway_smoke.py
```

Expected output includes:

```json
{
  "paid_status": 200,
  "payment_receipt": "accepted",
  "unpaid_status": 402
}
```

The smoke script redacts `ARC_LIVE_X_PAYMENT` and `CIRCLE_GATEWAY_API_KEY` from operator errors.

## Rollback

- Disable public traffic or scale the service to zero.
- Rotate `CIRCLE_GATEWAY_API_KEY` if logs or dashboards exposed it.
- Switch staging only back to `DOMAINFI_PAYMENT_MODE=local-demo` if you need to debug the HTTP loop without live payment verification.
- Re-run `python3 scripts/smoke_arc_paid_agent.py` locally before redeploying.

## What is intentionally not automated

- Creating a buyer payment proof.
- Moving USDC.
- Funding wallets.
- Deploying contracts.
- Storing or managing private keys.

Those require explicit operator action and current Circle/Arc documentation.
