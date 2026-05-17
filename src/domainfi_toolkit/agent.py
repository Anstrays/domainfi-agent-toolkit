"""High-level discovery agent.

Wires the provider, scoring pipeline, watchlists, and notifiers together. The
agent itself stays small on purpose: it is the place where the pieces meet,
not where business logic lives.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Generator, Iterable

from .models import Alert, Listing, Opportunity, Watchlist
from .notifiers import Notifier
from .providers import DomainProvider
from .scoring import score_domain
from .watchlist import domain_passes_hard_filters


@dataclass(frozen=True)
class ScanResult:
    """Metadata and results for one agent scan."""

    scanned_at: datetime
    watchlists: tuple[str, ...]
    candidates_total: int
    opportunities: tuple[Opportunity, ...]
    alerts_sent: int = 0

    @property
    def hit_rate(self) -> float:
        if self.candidates_total == 0:
            return 0.0
        return len(self.opportunities) / self.candidates_total

    def to_dict(self) -> dict:
        return {
            "scanned_at": self.scanned_at.isoformat(),
            "watchlists": list(self.watchlists),
            "candidates_total": self.candidates_total,
            "hit_rate": round(self.hit_rate, 4),
            "alerts_sent": self.alerts_sent,
            "opportunities": [opp.to_dict() for opp in self.opportunities],
        }


class DiscoveryAgent:
    def __init__(
        self,
        provider: DomainProvider,
        today: date | None = None,
        notifiers: Iterable[Notifier] | None = None,
    ) -> None:
        self._provider = provider
        self._today = today
        self._notifiers = list(notifiers or [])

    def scan(
        self,
        watchlists: Iterable[Watchlist],
        limit: int | None = None,
    ) -> list[Opportunity]:
        result = self.scan_once(watchlists=watchlists, limit=limit, notify=False)
        return list(result.opportunities)

    def scan_once(
        self,
        watchlists: Iterable[Watchlist],
        limit: int | None = None,
        *,
        notify: bool = False,
    ) -> ScanResult:
        watchlists = list(watchlists)
        domains = list(self._provider.list_domains())
        listings_by_domain: dict[str, Listing] = {
            listing.domain: listing
            for listing in self._provider.list_listings()
            if listing.status == "active"
        }

        opportunities: list[Opportunity] = []
        for watchlist in watchlists:
            for domain in domains:
                listing = listings_by_domain.get(domain.name)
                if not domain_passes_hard_filters(domain, watchlist, listing):
                    continue
                score = score_domain(domain, watchlist, listing=listing, today=self._today)
                if score.score < watchlist.min_score:
                    continue
                opportunities.append(
                    Opportunity(
                        domain=domain,
                        listing=listing,
                        score=score,
                        matched_watchlist=watchlist.name,
                    )
                )

        opportunities.sort(key=lambda opp: opp.score.score, reverse=True)
        if limit is not None:
            opportunities = opportunities[:limit]

        alerts_sent = 0
        if notify and self._notifiers:
            alerts = self.alerts_for(opportunities)
            for notifier in self._notifiers:
                alerts_sent += notifier.send(alerts)

        return ScanResult(
            scanned_at=datetime.now(timezone.utc),
            watchlists=tuple(watchlist.name for watchlist in watchlists),
            candidates_total=len(domains) * len(watchlists),
            opportunities=tuple(opportunities),
            alerts_sent=alerts_sent,
        )

    def scan_all(self, watchlists: Iterable[Watchlist], limit: int | None = None) -> list[ScanResult]:
        """Compatibility helper returning a list with one scan result."""

        return [self.scan_once(watchlists=watchlists, limit=limit)]

    def run_loop(
        self,
        watchlists: Iterable[Watchlist],
        *,
        interval_seconds: float,
        limit: int | None = None,
        iterations: int | None = None,
        notify: bool = True,
    ) -> Generator[ScanResult, None, None]:
        """Poll on a schedule and yield each scan result.

        ``iterations`` is optional so tests and short-lived jobs can terminate
        deterministically; omit it for a long-running watchdog loop.
        """

        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        completed = 0
        while iterations is None or completed < iterations:
            yield self.scan_once(watchlists=watchlists, limit=limit, notify=notify)
            completed += 1
            if iterations is None or completed < iterations:
                time.sleep(interval_seconds)

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
