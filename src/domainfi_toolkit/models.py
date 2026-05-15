"""Plain data models used across the toolkit.

Everything is a frozen dataclass so it is easy to reason about and
trivial to serialize. We deliberately avoid third-party validation
libraries to keep the prototype dependency-free.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class Domain:
    """A tokenized domain record returned by a provider."""

    name: str
    tld: str
    sld: str
    category: str | None = None
    tokenized: bool = True
    owner: str | None = None
    expires_at: str | None = None  # ISO 8601 date string

    def days_until_expiry(self, today: date | None = None) -> int | None:
        if not self.expires_at:
            return None
        try:
            target = date.fromisoformat(self.expires_at)
        except ValueError:
            return None
        reference = today or datetime.now(timezone.utc).date()
        return (target - reference).days


@dataclass(frozen=True)
class Listing:
    """A marketplace listing for a domain."""

    domain: str
    price_usd: float
    marketplace: str
    listed_at: str  # ISO 8601 datetime string
    status: str = "active"  # active | sold | expired | delisted


@dataclass(frozen=True)
class Watchlist:
    """A user-defined discovery strategy."""

    name: str
    keywords: tuple[str, ...] = ()
    tlds: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    max_price_usd: float | None = None
    min_score: int = 0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Watchlist":
        def _tuple(value: Any) -> tuple[str, ...]:
            if not value:
                return ()
            if isinstance(value, str):
                return (value.strip().lower(),)
            if isinstance(value, Iterable):
                return tuple(str(item).strip().lower() for item in value if str(item).strip())
            raise TypeError(f"expected list or string, got {type(value).__name__}")

        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("watchlist 'name' is required")

        max_price = payload.get("max_price_usd")
        if max_price is not None:
            try:
                max_price = float(max_price)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"watchlist '{name}': max_price_usd must be a number") from exc
            if max_price < 0:
                raise ValueError(f"watchlist '{name}': max_price_usd must be >= 0")

        min_score = int(payload.get("min_score") or 0)
        if not 0 <= min_score <= 100:
            raise ValueError(f"watchlist '{name}': min_score must be in 0..100")

        return cls(
            name=name,
            keywords=_tuple(payload.get("keywords")),
            tlds=_tuple(payload.get("tlds")),
            categories=_tuple(payload.get("categories")),
            max_price_usd=max_price,
            min_score=min_score,
        )


@dataclass(frozen=True)
class Signal:
    """A single, explainable contribution to a domain score."""

    name: str
    value: Any
    contribution: int
    explanation: str


@dataclass(frozen=True)
class ScoreResult:
    """The full score for a domain, with all contributing signals.

    Scores are clamped to the 0..100 range. Signals always carry an
    English-language explanation so the agent can show *why* a domain
    was ranked the way it was.
    """

    domain: str
    score: int
    signals: tuple[Signal, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "score": self.score,
            "signals": [asdict(signal) for signal in self.signals],
        }


@dataclass(frozen=True)
class Opportunity:
    """A scored domain plus its current listing (if any)."""

    domain: Domain
    listing: Listing | None
    score: ScoreResult
    matched_watchlist: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": asdict(self.domain),
            "listing": asdict(self.listing) if self.listing else None,
            "score": self.score.to_dict(),
            "matched_watchlist": self.matched_watchlist,
        }


@dataclass(frozen=True)
class Alert:
    """A user-visible message produced by the agent."""

    title: str
    body: str
    domain: str | None = None
    severity: str = "info"  # info | watchlist | expiry | price
