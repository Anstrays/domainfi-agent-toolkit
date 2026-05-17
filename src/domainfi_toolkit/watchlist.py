"""Watchlist loading and filtering helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Domain, Listing, Watchlist


def load_watchlists(path: str | Path) -> list[Watchlist]:
    """Load one or more watchlists from a JSON file.

    The file may contain either a single watchlist dict or a list of
    watchlist dicts. Validation errors are surfaced as ``ValueError``
    so the CLI can produce a friendly error message.
    """

    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("watchlist file must be a JSON object or array of objects")
    return [Watchlist.from_dict(item) for item in data]


def domain_passes_hard_filters(
    domain: Domain,
    watchlist: Watchlist,
    listing: Listing | None,
) -> bool:
    """Return True if a domain is allowed past the hard filters.

    Hard filters are independent of the score and reflect explicit
    user-configured limits (TLD allowlist, max price, category
    allowlist). Soft signals are handled by the scoring pipeline.
    """

    if watchlist.tlds and domain.tld not in watchlist.tlds:
        return False
    if watchlist.categories:
        if not domain.category or domain.category.lower() not in watchlist.categories:
            return False
    if watchlist.max_price_usd is not None and listing is not None:
        if listing.price_usd > watchlist.max_price_usd:
            return False
    return True
