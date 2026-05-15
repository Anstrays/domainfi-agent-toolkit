"""Domain data providers.

The ``DomainProvider`` protocol is the seam where Doma SDK/API access
will plug in. Until those endpoints are publicly accessible to this
project, the toolkit ships ``MockDomainProvider`` which loads a small
inventory from JSON. The provider boundary keeps scoring, watchlists,
and notifications fully testable without network access.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Protocol

from .models import Domain, Listing


class DomainProvider(Protocol):
    """Read-only interface for fetching domain inventory and listings."""

    def list_domains(self) -> Iterable[Domain]: ...

    def list_listings(self) -> Iterable[Listing]: ...


class MockDomainProvider:
    """Provider backed by a static JSON inventory.

    The inventory is intentionally small and synthetic. It is good
    enough to demonstrate scoring and watchlists end-to-end, while
    being obviously mock data so nobody confuses it with a real
    Doma feed.
    """

    def __init__(self, domains: list[Domain], listings: list[Listing]) -> None:
        self._domains = list(domains)
        self._listings = list(listings)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "MockDomainProvider":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_payload(data)

    @classmethod
    def from_payload(cls, payload: dict) -> "MockDomainProvider":
        domains = [_domain_from_dict(item) for item in payload.get("domains", [])]
        listings = [_listing_from_dict(item) for item in payload.get("listings", [])]
        return cls(domains=domains, listings=listings)

    @classmethod
    def default(cls) -> "MockDomainProvider":
        path = Path(__file__).parent / "data" / "sample_inventory.json"
        return cls.from_json_file(path)

    def list_domains(self) -> list[Domain]:
        return list(self._domains)

    def list_listings(self) -> list[Listing]:
        return list(self._listings)


def _domain_from_dict(item: dict) -> Domain:
    name = str(item["name"]).strip().lower()
    if "." not in name:
        raise ValueError(f"invalid domain name: {item['name']!r}")
    sld, _, tld = name.rpartition(".")
    return Domain(
        name=name,
        sld=sld,
        tld=tld,
        category=item.get("category"),
        tokenized=bool(item.get("tokenized", True)),
        owner=item.get("owner"),
        expires_at=item.get("expires_at"),
    )


def _listing_from_dict(item: dict) -> Listing:
    return Listing(
        domain=str(item["domain"]).strip().lower(),
        price_usd=float(item["price_usd"]),
        marketplace=str(item.get("marketplace", "unknown")),
        listed_at=str(item.get("listed_at", "")),
        status=str(item.get("status", "active")),
    )
