from __future__ import annotations

import unittest
from datetime import date

from domainfi_toolkit.agent import DiscoveryAgent
from domainfi_toolkit.models import Watchlist
from domainfi_toolkit.providers import MockDomainProvider


class DiscoveryAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockDomainProvider.default()
        self.today = date(2026, 5, 15)

    def test_results_sorted_by_score(self) -> None:
        wl = Watchlist.from_dict(
            {
                "name": "demo",
                "keywords": ["ai", "agent", "swap", "domainfi"],
                "categories": ["ai-tools", "domainfi", "defi"],
                "max_price_usd": 5000,
            }
        )
        agent = DiscoveryAgent(self.provider, today=self.today)
        results = agent.scan([wl])
        scores = [opp.score.score for opp in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_hard_filter_drops_over_budget_domain(self) -> None:
        wl = Watchlist.from_dict(
            {
                "name": "cheap",
                "max_price_usd": 1000,
                "categories": ["defi"],
            }
        )
        agent = DiscoveryAgent(self.provider, today=self.today)
        results = agent.scan([wl])
        for opp in results:
            self.assertEqual(opp.matched_watchlist, "cheap")
            if opp.listing:
                self.assertLessEqual(opp.listing.price_usd, 1000)

    def test_min_score_threshold(self) -> None:
        wl = Watchlist.from_dict({"name": "strict", "min_score": 95})
        agent = DiscoveryAgent(self.provider, today=self.today)
        results = agent.scan([wl])
        for opp in results:
            self.assertGreaterEqual(opp.score.score, 95)

    def test_limit_is_respected(self) -> None:
        wl = Watchlist.from_dict({"name": "open"})
        agent = DiscoveryAgent(self.provider, today=self.today)
        results = agent.scan([wl], limit=2)
        self.assertLessEqual(len(results), 2)

    def test_alerts_for_top_opportunities(self) -> None:
        wl = Watchlist.from_dict({"name": "open", "keywords": ["ai"]})
        agent = DiscoveryAgent(self.provider, today=self.today)
        results = agent.scan([wl], limit=3)
        alerts = DiscoveryAgent.alerts_for(results)
        self.assertEqual(len(alerts), len(results))
        for alert in alerts:
            self.assertEqual(alert.severity, "watchlist")
            self.assertTrue(alert.title)

    def test_scan_once_returns_metadata(self) -> None:
        wl = Watchlist.from_dict({"name": "open", "keywords": ["ai"]})
        agent = DiscoveryAgent(self.provider, today=self.today)
        result = agent.scan_once([wl], limit=2)
        self.assertEqual(result.watchlists, ("open",))
        self.assertLessEqual(len(result.opportunities), 2)
        self.assertGreater(result.candidates_total, 0)
        payload = result.to_dict()
        self.assertIn("hit_rate", payload)
        self.assertIn("opportunities", payload)

    def test_run_loop_can_be_bounded_for_jobs(self) -> None:
        wl = Watchlist.from_dict({"name": "open"})
        agent = DiscoveryAgent(self.provider, today=self.today)
        results = list(agent.run_loop([wl], interval_seconds=0.001, iterations=2, notify=False))
        self.assertEqual(len(results), 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
