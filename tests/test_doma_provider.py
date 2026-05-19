from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from domainfi_toolkit.providers import DomaHTTPProvider


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class DomaHTTPProviderTests(unittest.TestCase):
    def test_fetches_domains_and_listings_from_configurable_doma_api(self) -> None:
        calls = []

        def fake_urlopen(request, timeout=0):
            calls.append((request.full_url, request.headers, timeout))
            if request.full_url.endswith("/domains"):
                return _FakeResponse(
                    {
                        "domains": [
                            {
                                "name": "ArcAgent.com",
                                "category": "ai",
                                "tokenized": True,
                                "owner": "0xabc",
                                "expires_at": "2027-01-01",
                            }
                        ]
                    }
                )
            if request.full_url.endswith("/listings"):
                return _FakeResponse(
                    {
                        "listings": [
                            {
                                "domain": "ArcAgent.com",
                                "price_usd": "123.45",
                                "marketplace": "doma",
                                "listed_at": "2026-01-01T00:00:00Z",
                                "status": "active",
                            }
                        ]
                    }
                )
            raise AssertionError(request.full_url)

        with patch("domainfi_toolkit.providers.urlopen", fake_urlopen):
            provider = DomaHTTPProvider("https://api.example.test/v1", api_key="testtok", timeout_seconds=7)
            domains = provider.list_domains()
            listings = provider.list_listings()

        self.assertEqual(domains[0].name, "arcagent.com")
        self.assertEqual(domains[0].category, "ai")
        self.assertEqual(listings[0].domain, "arcagent.com")
        self.assertEqual(listings[0].price_usd, 123.45)
        self.assertEqual(calls[0][0], "https://api.example.test/v1/domains")
        self.assertEqual(calls[1][0], "https://api.example.test/v1/listings")
        self.assertEqual(calls[0][1]["Authorization"], "Bearer testtok")
        self.assertEqual(calls[0][2], 7)

    def test_api_key_is_redacted_from_network_errors(self) -> None:
        def fake_urlopen(request, timeout=0):
            raise OSError("failed with testtok in URL/log")

        with patch("domainfi_toolkit.providers.urlopen", fake_urlopen):
            provider = DomaHTTPProvider("https://api.example.test/v1", api_key="testtok")
            with self.assertRaisesRegex(RuntimeError, "\[REDACTED\]") as ctx:
                provider.list_domains()
        self.assertNotIn("testtok", str(ctx.exception))

    def test_rejects_unsafe_base_url(self) -> None:
        with self.assertRaises(ValueError):
            DomaHTTPProvider("file:///tmp/domains.json")


if __name__ == "__main__":
    unittest.main()
