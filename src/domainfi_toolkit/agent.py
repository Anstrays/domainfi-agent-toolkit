"""High-level discovery agent.

Wires the provider, scoring pipeline, watchlists, and notifiers
together. The agent itself stays small on purpose: it is the place
where the pieces meet, not where business logic lives.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from .models import Alert, Listing, Opportunity, Watchlist
from .providers import DomainProvider
from .scoring import score_domain
from .watchlist import domain_passes_hard_filters


class DiscoveryAgent:
    def __init__(self, provider: DomainProvider, today: date | None = None) -> None:
        self._provider = provider
        self._today = today

    def scan(
        self,
        watchlists: Iterable[Watchlist],
        limit: int | None = None,
    ) -> list[Opportunity]:
        domains = list(self._provider.list_domains())
        listings_by_domain: dict[str, Listing] = {
            listing.domain: listing
            for listing in self._provider.list_listings()
            if listing.status == "active"
        }

        results: list[Opportunity] = []
        for watchlist in watchlists:
            for domain in domains:
                listing = listings_by_domain.get(domain.name)
                if not domain_passes_hard_filters(domain, watchlist, listing):
                    continue
                score = score_domain(domain, watchlist, listing=listing, today=self._today)
                if score.score < watchlist.min_score:
                    continue
                results.append(
                    Opportunity(
                        domain=domain,
                        listing=listing,
                        score=score,
                        matched_watchlist=watchlist.name,
                    )
                )

        results.sort(key=lambda opp: opp.score.score, reverse=True)
        if limit is not None:
            results = results[:limit]
        return results

    @staticmethod
    def alerts_for(opportunities: Iterable[Opportunity]) -> list[Alert]:
        """Translate top opportunities into user-facing alerts."""

        alerts: list[Alert] = []
        for opp in opportunities:
            price_part = (
                f" at ${opp.listing.price_usd:.0f} on {opp.listing.marketplace}"
                if opp.listing
                else " (no active listing)"
            )
            top_signals = sorted(
                opp.score.signals,
                key=lambda signal: signal.contribution,
                reverse=True,
            )[:2]
            reason = "; ".join(signal.explanation for signal in top_signals if signal.contribution)
            alerts.append(
                Alert(
                    title=f"watchlist {opp.matched_watchlist!r}: score {opp.score.score}",
                    body=f"{opp.domain.name}{price_part}\nreason: {reason or 'baseline match'}",
                    domain=opp.domain.name,
                    severity="watchlist",
                )
            )
        return alerts
