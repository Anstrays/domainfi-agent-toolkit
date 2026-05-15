"""Transparent, explainable scoring.

The scoring pipeline is deliberately simple. Every signal is small,
deterministic, and carries a plain-English explanation so the agent
can answer "why is this domain ranked here?" honestly.

This is *not* a valuation model. It is a relevance + filterability
score against a user-defined ``Watchlist``. The number is bounded to
0..100.
"""

from __future__ import annotations

from datetime import date

from .models import Domain, Listing, ScoreResult, Signal, Watchlist


# Weights are kept as named constants so they are easy to audit.
_BRANDABILITY_MAX = 25
_KEYWORD_MAX = 30
_CATEGORY_MAX = 15
_TLD_MAX = 10
_PRICE_MAX = 15
_EXPIRY_MAX = 5


def score_domain(
    domain: Domain,
    watchlist: Watchlist,
    listing: Listing | None = None,
    today: date | None = None,
) -> ScoreResult:
    """Score a single domain against a watchlist."""

    signals: list[Signal] = []
    signals.append(_brandability_signal(domain))
    signals.append(_keyword_signal(domain, watchlist))
    signals.append(_category_signal(domain, watchlist))
    signals.append(_tld_signal(domain, watchlist))
    signals.append(_price_signal(listing, watchlist))
    signals.append(_expiry_signal(domain, today=today))

    raw = sum(signal.contribution for signal in signals)
    score = max(0, min(100, raw))
    return ScoreResult(domain=domain.name, score=score, signals=tuple(signals))


def _brandability_signal(domain: Domain) -> Signal:
    sld = domain.sld
    length = len(sld)
    has_separator = "-" in sld or any(ch.isdigit() for ch in sld)

    if length <= 5:
        contribution = _BRANDABILITY_MAX
        explanation = "very short SLD (<=5 chars), highly brandable"
    elif length <= 8:
        contribution = int(_BRANDABILITY_MAX * 0.8)
        explanation = "short SLD (6-8 chars), brandable"
    elif length <= 12:
        contribution = int(_BRANDABILITY_MAX * 0.5)
        explanation = "moderate SLD length (9-12 chars)"
    else:
        contribution = int(_BRANDABILITY_MAX * 0.2)
        explanation = "long SLD (>12 chars), less brandable"

    if has_separator:
        contribution = max(0, contribution - 5)
        explanation += "; contains hyphen or digit (penalty)"

    return Signal(
        name="brandability",
        value={"length": length, "has_separator_or_digit": has_separator},
        contribution=contribution,
        explanation=explanation,
    )


def _keyword_signal(domain: Domain, watchlist: Watchlist) -> Signal:
    if not watchlist.keywords:
        return Signal(
            name="keyword",
            value=None,
            contribution=0,
            explanation="no keywords configured in watchlist",
        )

    sld = domain.sld
    matched = [kw for kw in watchlist.keywords if kw and kw in sld]
    if not matched:
        return Signal(
            name="keyword",
            value=[],
            contribution=0,
            explanation="no watchlist keyword matched the SLD",
        )

    # Reward exact-match (sld == keyword) more than substring match.
    exact = any(sld == kw for kw in matched)
    if exact:
        contribution = _KEYWORD_MAX
        explanation = f"exact keyword match: {matched!r}"
    else:
        contribution = int(_KEYWORD_MAX * 0.6)
        explanation = f"substring keyword match: {matched!r}"

    return Signal(name="keyword", value=matched, contribution=contribution, explanation=explanation)


def _category_signal(domain: Domain, watchlist: Watchlist) -> Signal:
    if not watchlist.categories:
        return Signal(
            name="category",
            value=domain.category,
            contribution=0,
            explanation="no categories configured in watchlist",
        )
    if domain.category and domain.category.lower() in watchlist.categories:
        return Signal(
            name="category",
            value=domain.category,
            contribution=_CATEGORY_MAX,
            explanation=f"category {domain.category!r} matches watchlist",
        )
    return Signal(
        name="category",
        value=domain.category,
        contribution=0,
        explanation=f"category {domain.category!r} not in watchlist",
    )


def _tld_signal(domain: Domain, watchlist: Watchlist) -> Signal:
    if not watchlist.tlds:
        return Signal(
            name="tld",
            value=domain.tld,
            contribution=0,
            explanation="no TLD preferences configured",
        )
    if domain.tld in watchlist.tlds:
        return Signal(
            name="tld",
            value=domain.tld,
            contribution=_TLD_MAX,
            explanation=f"TLD .{domain.tld} matches watchlist",
        )
    return Signal(
        name="tld",
        value=domain.tld,
        contribution=0,
        explanation=f"TLD .{domain.tld} not in watchlist",
    )


def _price_signal(listing: Listing | None, watchlist: Watchlist) -> Signal:
    if listing is None:
        return Signal(
            name="price",
            value=None,
            contribution=0,
            explanation="no active listing for this domain",
        )
    if watchlist.max_price_usd is None:
        return Signal(
            name="price",
            value=listing.price_usd,
            contribution=int(_PRICE_MAX * 0.4),
            explanation="listing exists; no max_price filter configured",
        )
    if listing.price_usd > watchlist.max_price_usd:
        return Signal(
            name="price",
            value=listing.price_usd,
            contribution=0,
            explanation=(
                f"price ${listing.price_usd:.0f} exceeds watchlist cap "
                f"${watchlist.max_price_usd:.0f}"
            ),
        )
    # Linear reward: cheaper relative to the cap = higher contribution.
    ratio = listing.price_usd / watchlist.max_price_usd if watchlist.max_price_usd else 1.0
    contribution = int(round(_PRICE_MAX * (1 - min(1.0, ratio))))
    contribution = max(1, contribution)  # never zero out a within-budget listing
    return Signal(
        name="price",
        value=listing.price_usd,
        contribution=contribution,
        explanation=(
            f"price ${listing.price_usd:.0f} within cap "
            f"${watchlist.max_price_usd:.0f}"
        ),
    )


def _expiry_signal(domain: Domain, today: date | None = None) -> Signal:
    days = domain.days_until_expiry(today=today)
    if days is None:
        return Signal(
            name="expiry",
            value=None,
            contribution=0,
            explanation="no expiry date available",
        )
    if days < 0:
        return Signal(
            name="expiry",
            value=days,
            contribution=0,
            explanation=f"expired {abs(days)} day(s) ago",
        )
    if days <= 30:
        return Signal(
            name="expiry",
            value=days,
            contribution=_EXPIRY_MAX,
            explanation=f"expires soon (in {days} day(s))",
        )
    if days <= 180:
        return Signal(
            name="expiry",
            value=days,
            contribution=int(_EXPIRY_MAX * 0.6),
            explanation=f"expires within 6 months (in {days} day(s))",
        )
    return Signal(
        name="expiry",
        value=days,
        contribution=0,
        explanation=f"expiry far away ({days} day(s))",
    )
