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

    def test_string_keyword_is_not_split_into_characters(self) -> None:
        # ``str`` is itself an Iterable; ensure we treat it as a single
        # value, not a sequence of characters.
        wl = Watchlist.from_dict({"name": "demo", "keywords": "swap"})
        self.assertEqual(wl.keywords, ("swap",))
        self.assertNotIn("s", wl.keywords)

    def test_bytes_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            Watchlist.from_dict({"name": "demo", "keywords": b"swap"})

    def test_tuple_input_is_accepted(self) -> None:
        wl = Watchlist.from_dict({"name": "demo", "keywords": ("AI", "Swap")})
        self.assertEqual(wl.keywords, ("ai", "swap"))

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


class DomainFromNameTests(unittest.TestCase):
    def test_derives_sld_and_tld(self) -> None:
        domain = Domain.from_name("Foo.Example")
        self.assertEqual(domain.name, "foo.example")
        self.assertEqual(domain.sld, "foo")
        self.assertEqual(domain.tld, "example")

    def test_subdomain_is_treated_as_sld(self) -> None:
        # rpartition keeps the rightmost label as the TLD; the rest is the SLD.
        domain = Domain.from_name("api.foo.example")
        self.assertEqual(domain.sld, "api.foo")
        self.assertEqual(domain.tld, "example")

    def test_rejects_name_without_dot(self) -> None:
        with self.assertRaises(ValueError):
            Domain.from_name("nodot")

    def test_rejects_empty_label(self) -> None:
        with self.assertRaises(ValueError):
            Domain.from_name(".example")
        with self.assertRaises(ValueError):
            Domain.from_name("foo.")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
