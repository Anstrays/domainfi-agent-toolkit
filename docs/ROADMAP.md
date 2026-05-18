# Roadmap

## Phase 0 — Proposal page

- [x] Public GitHub repository
- [x] GitHub Pages project site
- [x] README with project scope
- [x] Security policy
- [x] Architecture notes

## Phase 1 — Doma research and integration design

- [ ] Review Doma SDK/API/testnet documentation
- [ ] Identify domain inventory, ownership, listing, and event endpoints
- [ ] Define local data model for domains, watchlists, portfolios, and alerts
- [ ] Publish integration notes

## Phase 2 — Discovery prototype

- [x] Implement Doma data adapter stub (`MockDomainProvider`)
- [x] Add domain filtering and watchlist configuration
- [x] Build transparent scoring pipeline
- [x] Output ranked results with explanations
- [x] Add CLI demo (`python -m domainfi_toolkit scan ...`)

## Phase 3 — Alerts and portfolio monitoring

- [ ] Add portfolio/watchlist persistence
- [ ] Add scheduled monitoring job
- [ ] Add Telegram notification adapter
- [ ] Add Discord notification adapter
- [ ] Add alert deduplication and rate limits

## Phase 4 — Builder templates

- [x] Arc x402 paid discovery agent example
- [x] Arc Testnet runbook and USDC unit economics
- [ ] Example Telegram bot
- [ ] Example Discord bot
- [ ] Example webhook receiver
- [ ] Example analytics dashboard data export
- [ ] Setup guide and technical write-up

## Phase 5 — Safety and production hardening

- [ ] Input validation test suite
- [ ] Secret handling guide
- [ ] Rate-limit and retry policy
- [ ] Structured logging with redaction
- [ ] Human-confirmation flow for any state-changing action
