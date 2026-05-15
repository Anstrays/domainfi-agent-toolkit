from __future__ import annotations

import unittest
from datetime import date

from domainfi_toolkit.models import Domain, Watchlist


class WatchlistFromDictTests(unittest.TestCase):
    def test_minimal_watchlist(self) -> None:
        wl = Watchlist.from_dict({"name": "demo"})
        self.assertEqual(wl.name, "demo")
        self.assertEqual(wl.keywords, ())
        self.assertEqual(wl.tlds, ())
        self.assertIsNone(wl.max_price_usd)
        self.assertEqual(wl.min_score, 0)

    def test_lists_are_lowercased_and_trimmed(self) -> None:
        wl = Watchlist.from_dict(
            {
                "name": "demo",
                "keywords": ["AI", " swap "],
                "tlds": ["EXAMPLE"],
                "categories": ["DeFi"],
            }
        )
        self.assertEqual(wl.keywords, ("ai", "swap"))
        self.assertEqual(wl.tlds, ("example",))
        self.assertEqual(wl.categories, ("defi",))

    def test_string_value_becomes_single_tuple(self) -> None:
        wl = Watchlist.from_dict({"name": "demo", "keywords": "ai"})
        self.assertEqual(wl.keywords, ("ai",))

    def test_missing_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Watchlist.from_dict({"keywords": ["ai"]})

    def test_negative_max_price_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Watchlist.from_dict({"name": "demo", "max_price_usd": -1})

    def test_invalid_max_price_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Watchlist.from_dict({"name": "demo", "max_price_usd": "free"})

    def test_min_score_out_of_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Watchlist.from_dict({"name": "demo", "min_score": 200})


class DomainExpiryTests(unittest.TestCase):
    def test_days_until_expiry(self) -> None:
        domain = Domain(name="x.example", sld="x", tld="example", expires_at="2026-06-01")
        self.assertEqual(domain.days_until_expiry(today=date(2026, 5, 15)), 17)

    def test_no_expiry(self) -> None:
        domain = Domain(name="x.example", sld="x", tld="example")
        self.assertIsNone(domain.days_until_expiry(today=date(2026, 5, 15)))

    def test_invalid_expiry(self) -> None:
        domain = Domain(name="x.example", sld="x", tld="example", expires_at="not-a-date")
        self.assertIsNone(domain.days_until_expiry(today=date(2026, 5, 15)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
