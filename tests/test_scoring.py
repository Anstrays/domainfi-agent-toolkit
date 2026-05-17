from __future__ import annotations

import unittest
from datetime import date

from domainfi_toolkit.models import Domain, Listing, Watchlist
from domainfi_toolkit.scoring import score_domain


def make_domain(name: str = "agent.example", **kwargs) -> Domain:
    sld, _, tld = name.partition(".")
    return Domain(name=name, sld=sld, tld=tld, **kwargs)


class ScoreDomainTests(unittest.TestCase):
    def test_score_is_clamped_to_0_100(self) -> None:
        domain = make_domain("ai.example", category="ai-tools", expires_at="2026-06-01")
        listing = Listing(
            domain=domain.name,
            price_usd=100.0,
            marketplace="m",
            listed_at="2026-05-01T00:00:00Z",
        )
        wl = Watchlist.from_dict(
            {
                "name": "demo",
                "keywords": ["ai"],
                "tlds": ["example"],
                "categories": ["ai-tools"],
                "max_price_usd": 1000,
            }
        )
        result = score_domain(domain, wl, listing=listing, today=date(2026, 5, 15))
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)
        self.assertEqual(result.domain, domain.name)

    def test_keyword_exact_match_beats_substring(self) -> None:
        domain_exact = make_domain("ai.example")
        domain_sub = make_domain("aimagic.example")
        wl = Watchlist.from_dict({"name": "demo", "keywords": ["ai"]})
        exact = score_domain(domain_exact, wl)
        substring = score_domain(domain_sub, wl)
        keyword_exact = next(s for s in exact.signals if s.name == "keyword")
        keyword_sub = next(s for s in substring.signals if s.name == "keyword")
        self.assertGreater(keyword_exact.contribution, keyword_sub.contribution)

    def test_price_over_cap_zero_contribution(self) -> None:
        domain = make_domain("yield.example", category="defi")
        listing = Listing(
            domain=domain.name,
            price_usd=20000.0,
            marketplace="m",
            listed_at="2026-05-01T00:00:00Z",
        )
        wl = Watchlist.from_dict({"name": "demo", "max_price_usd": 1000})
        result = score_domain(domain, wl, listing=listing)
        price = next(s for s in result.signals if s.name == "price")
        self.assertEqual(price.contribution, 0)

    def test_brandability_short_beats_long(self) -> None:
        wl = Watchlist.from_dict({"name": "demo"})
        short = score_domain(make_domain("ai.example"), wl)
        longer = score_domain(make_domain("longish-domain-name.example"), wl)
        b_short = next(s for s in short.signals if s.name == "brandability")
        b_long = next(s for s in longer.signals if s.name == "brandability")
        self.assertGreater(b_short.contribution, b_long.contribution)

    def test_expiry_soon_signal(self) -> None:
        domain = make_domain("x.example", expires_at="2026-05-20")
        wl = Watchlist.from_dict({"name": "demo"})
        result = score_domain(domain, wl, today=date(2026, 5, 15))
        expiry = next(s for s in result.signals if s.name == "expiry")
        self.assertGreater(expiry.contribution, 0)
        self.assertIn("expires soon", expiry.explanation)

    def test_signals_have_explanations(self) -> None:
        domain = make_domain("ai.example")
        wl = Watchlist.from_dict({"name": "demo"})
        result = score_domain(domain, wl)
        for signal in result.signals:
            self.assertTrue(signal.explanation, f"missing explanation for {signal.name}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
