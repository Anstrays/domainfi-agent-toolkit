# DomainFi Agent Toolkit

AI-powered agents and developer templates for discovering, monitoring, and acting on tokenized domain opportunities on Doma Protocol.

[![Validate static site](https://github.com/Anstrays/domainfi-agent-toolkit/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/Anstrays/domainfi-agent-toolkit/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status: proposal](https://img.shields.io/badge/status-proposal%20%26%20prototype-7cf7c9)](docs/ROADMAP.md)
[![GitHub Pages](https://img.shields.io/badge/site-anstrays.github.io-78a8ff?logo=githubpages&logoColor=white)](https://anstrays.github.io/domainfi-agent-toolkit/)

[Live project page](https://anstrays.github.io/domainfi-agent-toolkit/) · [Architecture](docs/ARCHITECTURE.md) · [Arc MVP](docs/ARC_MVP.md) · [Roadmap](docs/ROADMAP.md) · [Grant scope](docs/GRANT_SCOPE.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

> Status: early Doma Forge grant proposal and prototype scope. The repository now ships a small dependency-free Python prototype of the discovery agent (mock data, transparent scoring, watchlists, CLI). Production Doma integrations will be added behind the same provider interface once SDK/API/testnet access is available.

## Table of contents

- [Why this exists](#why-this-exists)
- [Quickstart](#quickstart)
- [Initial workflows](#initial-workflows)
- [Planned Doma integration](#planned-doma-integration)
- [Arc paid-agent MVP](#arc-paid-agent-mvp)
- [Proposed milestones](#proposed-milestones)
- [Tech direction](#tech-direction)
- [Local development](#local-development)
- [Security posture](#security-posture)
- [Doma Forge application summary](#doma-forge-application-summary)
- [License](#license)

## Why this exists

DomainFi turns domains into programmable onchain assets. Domain markets are information-heavy: users need discovery, filtering, valuation signals, portfolio monitoring, expiry tracking, marketplace alerts, and developer-friendly integration examples.

DomainFi Agent Toolkit is designed as an agent layer around Doma Protocol: a practical set of bots, scripts, and templates that help users and developers turn raw domain data into useful workflows.

## Quickstart

The repository ships a small Python prototype (no external dependencies, Python 3.10+). It uses a mock inventory so the pipeline can be exercised without Doma SDK/API access.

```bash
# 1. Show the version
PYTHONPATH=src python3 -m domainfi_toolkit version

# 2. Scan the bundled mock inventory against an example watchlist
PYTHONPATH=src python3 -m domainfi_toolkit scan \
    --watchlist examples/watchlists/brandable-ai.json

# 3. Same scan, machine-readable output
PYTHONPATH=src python3 -m domainfi_toolkit scan \
    --watchlist examples/watchlists/brandable-ai.json --json --limit 5

# 4. Run the test suite (uses only the standard library)
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Or install it as a console script:

```bash
pip install -e .
domainfi-agent scan --watchlist examples/watchlists/brandable-ai.json
```

The scoring pipeline is intentionally transparent: every signal carries an explanation, and the score is bounded to 0..100. See [`src/domainfi_toolkit/scoring.py`](src/domainfi_toolkit/scoring.py).

## Initial workflows

### 1. Domain discovery agent

Scans domain inventory and marketplace data, then ranks opportunities by:

- relevance to a user-defined niche or strategy
- category and brandability
- pricing and liquidity signals
- marketplace activity
- configurable filters and watchlists

### 2. Portfolio and alerts agent

Tracks domain ownership and market events, then sends actionable alerts through Telegram or Discord:

- owned domain status changes
- expiry and renewal reminders
- pricing changes
- marketplace activity
- watchlist matches

### 3. Developer integration templates

Starter examples for builders who want to integrate Doma-powered domain data into:

- Telegram/Discord bots
- analytics dashboards
- portfolio tools
- marketplaces
- AI-agent workflows
- wallet or domain management interfaces

## Planned Doma integration

The toolkit is intended to integrate with Doma Protocol through available SDKs, APIs, marketplace data, and onchain domain primitives.

Potential modules:

- Doma API client wrapper
- domain inventory queries
- ownership/status tracking
- marketplace event monitoring
- scoring and filtering pipeline
- notification adapters
- agent prompts and workflow templates

## Arc paid-agent MVP

The repo now includes an Arc/Circle-native monetization wedge: a dependency-free paid discovery endpoint demo using an x402-style HTTP `402 Payment Required` flow.

```bash
# Print Arc Testnet config, x402 challenge payload, and unit economics
PYTHONPATH=src python3 -m domainfi_toolkit arc-mvp --json

# Print the MCP-style Arc paid-agent tool manifest for coding agents
PYTHONPATH=src python3 -m domainfi_toolkit arc-tools --json

# Build a single payment intent and local demo proof
PYTHONPATH=src python3 -m domainfi_toolkit arc-intent \
    --resource domainfi.discovery.scan \
    --price-microusd 25000 \
    --json

# Verify a local demo payment proof and receive a machine-readable receipt
PYTHONPATH=src python3 -m domainfi_toolkit arc-verify \
    --payment 'x402-test:domainfi.discovery.scan:25000' \
    --json

# Verify an opaque production x402 proof against a configured Circle Gateway verifier
CIRCLE_GATEWAY_URL=https://gateway.example.test/v1 \
CIRCLE_GATEWAY_API_KEY=redacted \
PYTHONPATH=src python3 -m domainfi_toolkit arc-gateway-verify \
    --payment '<opaque-x402-proof>' \
    --json

# Run the local paid agent endpoint
PYTHONPATH=src python3 examples/arc-x402-paid-agent/server.py --port 8765

# Run the paid endpoint in Gateway verification mode
DOMAINFI_PAYMENT_MODE=gateway \
CIRCLE_GATEWAY_URL=https://gateway.example.test/v1 \
CIRCLE_GATEWAY_API_KEY=redacted \
PYTHONPATH=src python3 examples/arc-x402-paid-agent/server.py --port 8765

# Or run the full local smoke test: server boot, unpaid 402, paid 200, receipt check
python3 scripts/smoke_arc_paid_agent.py

# Expose the same Arc tools over a minimal JSON-RPC/MCP-style stdio server
printf '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n' | \
    PYTHONPATH=src python3 -m domainfi_toolkit.arc_mcp

# Request without payment: returns 402 payment instructions
python3 examples/arc-x402-paid-agent/client.py --url http://127.0.0.1:8765/scan

# Request with the local demo payment proof: returns paid discovery JSON
python3 examples/arc-x402-paid-agent/client.py \
    --url http://127.0.0.1:8765/scan \
    --payment 'x402-test:domainfi.discovery.scan:25000'
```

Arc fit: USDC-native gas, sub-second finality, EVM compatibility, and Circle Gateway/x402 make paid domain intelligence practical as pay-per-scan, pay-per-alert, and pay-per-API-call workflows. See [`docs/ARC_MVP.md`](docs/ARC_MVP.md) and [`examples/arc-x402-paid-agent/`](examples/arc-x402-paid-agent/).

## Proposed milestones

| Milestone | Scope | Output |
| --- | --- | --- |
| 1. Research and architecture | Map Doma docs, SDKs, APIs, data surfaces, and event model | Architecture notes and integration plan |
| 2. Prototype agent | Domain discovery CLI/bot with filters, watchlists, ranked output, and explanations | Working local prototype |
| 3. Alerts and templates | Telegram/Discord notification example and portfolio/watchlist monitoring flow | Documented starter templates |
| 4. Public demo and write-up | Public demo, setup guide, and technical article | Builder-facing DomainFi agent example |

## Tech direction

The first prototype is expected to use:

- TypeScript or Python for integration code
- Telegram/Discord bot adapters
- scheduled jobs for monitoring
- lightweight browser/API automation where needed
- modular provider interface for Doma data sources

## Local development

The repository now contains both a static landing page and a small Python package. Both are dependency-free.

### Static site

```bash
# Option A: open the file directly
xdg-open index.html        # Linux
open index.html            # macOS

# Option B: serve over HTTP (recommended, matches GitHub Pages)
python3 -m http.server 8080
# then visit http://localhost:8080/
```

### Python prototype

```bash
# Run the unit tests (standard library only, no install required)
PYTHONPATH=src python3 -m unittest discover -s tests -v

# Run the CLI without installing
PYTHONPATH=src python3 -m domainfi_toolkit scan \
    --watchlist examples/watchlists/brandable-ai.json

# Or install in editable mode and use the console script
pip install -e .
domainfi-agent scan --watchlist examples/watchlists/brandable-ai.json
```

### Repository validator

```bash
python3 scripts/validate_repo.py
```

The validator is dependency-free and verifies:

- required documents are present
- no obvious secret patterns are committed
- `index.html` ships safe HTML (no executable scripts, no inline event handlers, no broken anchors, external links carry `rel="noopener noreferrer"`, images have `alt` text, basic SEO meta tags are present)

## Security posture

This repository intentionally contains no secrets, API keys, backend service, wallet keys, or production credentials. Future integrations will use environment variables and documented least-privilege configuration. See [SECURITY.md](SECURITY.md).

## Doma Forge application summary

This project aims to make DomainFi easier to use through assistants that can search, monitor, explain, rank, and notify. The goal is to help Doma onboard developers, domain investors, crypto-native traders, and users who need practical workflows rather than raw data.

## License

MIT
