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
import json
from pathlib import Path

from .models import Domain, Listing, ScoreResult, Signal, Watchlist


# Weights are kept as named constants so they are easy to audit.
# Each ``_*_MAX`` is the maximum positive contribution that signal can add to
# the raw score. The weights are designed to sum to ``_TOTAL_MAX`` so a
# perfect match in every dimension lands exactly at 100.
_BRANDABILITY_MAX = 25
_KEYWORD_MAX = 30
_CATEGORY_MAX = 15
_TLD_MAX = 10
_PRICE_MAX = 15
_EXPIRY_MAX = 5
_TOTAL_MAX = 100
_DEFAULT_WEIGHTS = {
    "brandability": _BRANDABILITY_MAX,
    "keyword": _KEYWORD_MAX,
    "category": _CATEGORY_MAX,
    "tld": _TLD_MAX,
    "price": _PRICE_MAX,
    "expiry": _EXPIRY_MAX,
}
_active_weights = dict(_DEFAULT_WEIGHTS)

# Fail loudly at import time if a future edit breaks the 0..100 invariant.
_WEIGHTS_SUM = (
    _BRANDABILITY_MAX
    + _KEYWORD_MAX
    + _CATEGORY_MAX
    + _TLD_MAX
    + _PRICE_MAX
    + _EXPIRY_MAX
)
assert _WEIGHTS_SUM == _TOTAL_MAX, (
    f"scoring weights must sum to {_TOTAL_MAX}, got {_WEIGHTS_SUM}"
)
assert sum(_DEFAULT_WEIGHTS.values()) == _TOTAL_MAX


def _weight(name: str) -> int:
    return _active_weights[name]


def _coerce_weight(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"weight {name!r} must be an integer")
    return value


def reset_weights() -> None:
    """Restore default scoring weights."""

    _active_weights.clear()
    _active_weights.update(_DEFAULT_WEIGHTS)


def load_weights(path: str | Path) -> None:
    """Load runtime scoring weights from JSON.

    The JSON object must provide all signal names and the weights must sum to
    100. This keeps custom scoring explainable while preserving the invariant
    expected by tests and CLI users.
    """

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("weights file must contain a JSON object")
    missing = set(_DEFAULT_WEIGHTS) - set(payload)
    extra = set(payload) - set(_DEFAULT_WEIGHTS)
    if missing or extra:
        raise ValueError(f"weights keys mismatch; missing={sorted(missing)} extra={sorted(extra)}")
    weights = {name: _coerce_weight(name, value) for name, value in payload.items()}
    if any(value < 0 for value in weights.values()):
        raise ValueError("weights must be non-negative")
    if sum(weights.values()) != _TOTAL_MAX:
        raise ValueError(f"weights must sum to {_TOTAL_MAX}, got {sum(weights.values())}")
    _active_weights.clear()
    _active_weights.update(weights)


def explain(result: ScoreResult) -> str:
    """Return a compact human-readable score breakdown."""

    parts = [f"{result.domain}: {result.score}/100"]
    for signal in result.signals:
        if signal.contribution:
            parts.append(f"{signal.name} +{signal.contribution}: {signal.explanation}")
    return " | ".join(parts)


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
    score = max(0, min(_TOTAL_MAX, raw))
    return ScoreResult(domain=domain.name, score=score, signals=tuple(signals))


def _brandability_signal(domain: Domain) -> Signal:
    sld = domain.sld
    length = len(sld)
    has_separator = "-" in sld or any(ch.isdigit() for ch in sld)

    if length <= 5:
        contribution = _weight("brandability")
        explanation = "very short SLD (<=5 chars), highly brandable"
    elif length <= 8:
        contribution = int(_weight("brandability") * 0.8)
        explanation = "short SLD (6-8 chars), brandable"
    elif length <= 12:
        contribution = int(_weight("brandability") * 0.5)
        explanation = "moderate SLD length (9-12 chars)"
    else:
        contribution = int(_weight("brandability") * 0.2)
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
        contribution = _weight("keyword")
        explanation = f"exact keyword match: {matched!r}"
    else:
        contribution = int(_weight("keyword") * 0.6)
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
            contribution=_weight("category"),
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
            contribution=_weight("tld"),
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
            contribution=int(_weight("price") * 0.4),
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
    contribution = int(round(_weight("price") * (1 - min(1.0, ratio))))
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
            contribution=_weight("expiry"),
            explanation=f"expires soon (in {days} day(s))",
        )
    if days <= 180:
        return Signal(
            name="expiry",
            value=days,
            contribution=int(_weight("expiry") * 0.6),
            explanation=f"expires within 6 months (in {days} day(s))",
        )
    return Signal(
        name="expiry",
        value=days,
        contribution=0,
        explanation=f"expiry far away ({days} day(s))",
    )
