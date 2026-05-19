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
from typing import Any, Iterable, Protocol
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

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


class DomaHTTPProvider:
    """Read Doma-compatible domain/listing JSON over HTTPS.

    The public Doma API surface is still evolving, so this provider keeps the
    integration seam deliberately small and configurable: operators pass the
    base URL and optional bearer token via CLI/env, while the scanner consumes
    the same ``DomainProvider`` protocol as the mock provider. Accepted response
    shapes are intentionally permissive: either ``{"domains": [...]}`` /
    ``{"listings": [...]}`` envelopes or bare arrays.
    """

    def __init__(self, base_url: str, *, api_key: str | None = None, timeout_seconds: int = 20) -> None:
        clean_url = str(base_url or "").strip().rstrip("/") + "/"
        parsed = urlparse(clean_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Doma API URL must be an http(s) URL")
        if isinstance(timeout_seconds, bool) or int(timeout_seconds) <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self.base_url = clean_url
        self.api_key = str(api_key).strip() if api_key else None
        self.timeout_seconds = int(timeout_seconds)

    def list_domains(self) -> list[Domain]:
        payload = self._get_json("domains")
        items = payload if isinstance(payload, list) else payload.get("domains", [])
        if not isinstance(items, list):
            raise RuntimeError("Doma domains response must be a list or contain a domains list")
        return [_domain_from_dict(item) for item in items]

    def list_listings(self) -> list[Listing]:
        payload = self._get_json("listings")
        items = payload if isinstance(payload, list) else payload.get("listings", [])
        if not isinstance(items, list):
            raise RuntimeError("Doma listings response must be a list or contain a listings list")
        return [_listing_from_dict(item) for item in items]

    def _get_json(self, path: str) -> Any:
        url = urljoin(self.base_url, path)
        headers = {"Accept": "application/json", "User-Agent": "domainfi-agent-toolkit/0.1"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - redact before surfacing any transport failure.
            raise RuntimeError(f"failed to fetch Doma API {path}: {self._redact(str(exc))}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Doma API {path} did not return valid JSON") from exc

    def _redact(self, text: str) -> str:
        if self.api_key:
            return text.replace(self.api_key, "[REDACTED]")
        return text


def _domain_from_dict(item: dict) -> Domain:
    return Domain.from_name(
        item["name"],
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
