# DomainFi Agent Toolkit

AI-powered agents and developer templates for discovering, monitoring, and acting on tokenized domain opportunities on Doma Protocol.

> Status: early grant proposal / prototype scope for Doma Forge.

## Why this exists

DomainFi turns domains into programmable onchain assets. But domain markets are information-heavy: users need discovery, filtering, valuation signals, portfolio monitoring, expiry tracking, marketplace alerts, and developer-friendly integration examples.

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

### Milestone 1 — Research and architecture

- map Doma docs, SDKs, APIs, and event surfaces
- define core data model for domains, watchlists, alerts, and scoring
- publish architecture notes and initial integration plan

### Milestone 2 — Prototype agent

- build domain discovery CLI / bot prototype
- add configurable filters and watchlists
- produce ranked output with explanation traces

### Milestone 3 — Alerts and developer templates

- Telegram/Discord notification example
- portfolio/watchlist monitoring flow
- documented starter templates for builders

### Milestone 4 — Public demo and write-up

- public demo repository
- setup guide
- technical article: building agentic DomainFi workflows on Doma

## Tech direction

The first prototype is expected to use:

- TypeScript or Python for integration code
- Telegram/Discord bot adapters
- scheduled jobs for monitoring
- lightweight browser/API automation where needed
- modular provider interface for Doma data sources

## Doma Forge application summary

This project aims to make DomainFi easier to use through assistants that can search, monitor, explain, rank, and notify. The goal is to help Doma onboard developers, domain investors, crypto-native traders, and users who need practical workflows rather than raw data.

## License

MIT
