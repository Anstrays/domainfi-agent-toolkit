# Architecture

DomainFi Agent Toolkit is planned as a modular agent layer around Doma Protocol.

## High-level flow

```text
Doma SDK / API / marketplace events
        ↓
Data adapters
        ↓
Normalization and scoring
        ↓
Watchlists / portfolio state
        ↓
Agent workflows
        ↓
Telegram, Discord, CLI, webhook, dashboard
```

## Components

### 1. Doma data adapter

Responsible for fetching and normalizing Doma-powered domain data.

Planned responsibilities:

- domain inventory queries
- ownership/status lookups
- marketplace listing reads
- event polling or webhook handling
- retry and rate-limit handling

### 2. Domain scoring pipeline

Turns raw domain records into ranked opportunities.

Possible signals:

- exact match with a user-defined theme
- length and readability
- category fit
- pricing movement
- marketplace activity
- renewal/expiry timing
- watchlist match

The first implementation should keep scoring transparent and explainable rather than pretending to produce a universal valuation model.

### 3. Watchlist and portfolio state

Tracks user-defined strategies and relevant domain state.

Example data:

- watched keywords
- preferred TLDs/categories
- max price thresholds
- owned domains
- alert frequency
- ignored domains

### 4. Notification adapters

Sends useful, low-noise alerts to user-facing channels.

Initial targets:

- Telegram
- Discord
- CLI output
- webhook

### 5. Developer templates

Small examples that other builders can copy and adapt:

- domain discovery bot
- portfolio monitor
- marketplace alert webhook
- scoring pipeline example
- Doma API wrapper example

## Trust boundaries

All external data should be treated as untrusted:

- domain names
- listing metadata
- user filters
- URLs
- wallet addresses
- notification destinations
- agent-generated text

Any future action that changes ownership, spends funds, lists domains, buys domains, or updates portfolio state should require explicit user confirmation.

## Non-goals for the first milestone

- no custody of user funds
- no private key handling
- no automated domain purchases
- no automated listings or transfers
- no hidden valuation claims
- no scraping-heavy workflows if official Doma APIs are available
