# DomainFi Agent Toolkit

AI-powered agents and developer templates for discovering, monitoring, and acting on tokenized domain opportunities on Doma Protocol.

[Live project page](https://anstrays.github.io/domainfi-agent-toolkit/) · [Architecture](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md) · [Security](SECURITY.md)

> Status: early Doma Forge grant proposal and prototype scope. This repository currently contains the public project page and technical plan; production Doma integrations will be added after SDK/API/testnet access is available.

## Why this exists

DomainFi turns domains into programmable onchain assets. Domain markets are information-heavy: users need discovery, filtering, valuation signals, portfolio monitoring, expiry tracking, marketplace alerts, and developer-friendly integration examples.

DomainFi Agent Toolkit is designed as an agent layer around Doma Protocol: a practical set of bots, scripts, and templates that help users and developers turn raw domain data into useful workflows.

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

## Security posture

This repository intentionally contains no secrets, API keys, backend service, wallet keys, or production credentials. Future integrations will use environment variables and documented least-privilege configuration. See [SECURITY.md](SECURITY.md).

## Doma Forge application summary

This project aims to make DomainFi easier to use through assistants that can search, monitor, explain, rank, and notify. The goal is to help Doma onboard developers, domain investors, crypto-native traders, and users who need practical workflows rather than raw data.

## License

MIT
