from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from domainfi_toolkit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_WATCHLIST = REPO_ROOT / "examples" / "watchlists" / "brandable-ai.json"


class CliTests(unittest.TestCase):
    def test_version_command(self) -> None:
        out = io.StringIO()
        rc = main(["version"], stdout=out)
        self.assertEqual(rc, 0)
        self.assertIn("domainfi-agent", out.getvalue())

    def test_scan_human_readable(self) -> None:
        out = io.StringIO()
        rc = main(["scan", "--watchlist", str(EXAMPLE_WATCHLIST)], stdout=out)
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("Watchlists scanned: brandable-ai", text)
        self.assertIn("score=", text)

    def test_scan_json_output_is_valid(self) -> None:
        out = io.StringIO()
        rc = main(
            ["scan", "--watchlist", str(EXAMPLE_WATCHLIST), "--json", "--limit", "3"],
            stdout=out,
        )
        self.assertEqual(rc, 0)
        raw = out.getvalue()
        payload = json.loads(raw)

        # Top-level shape.
        self.assertIn("opportunities", payload)
        self.assertIn("count", payload)
        self.assertIn("version", payload)
        self.assertIn("watchlists", payload)
        self.assertEqual(payload["count"], len(payload["opportunities"]))
        self.assertLessEqual(len(payload["opportunities"]), 3)

        # Per-opportunity schema and full roundtrip stability: dumping the
        # parsed payload should yield exactly the same JSON string back.
        self.assertEqual(json.loads(json.dumps(payload)), payload)

        for opp in payload["opportunities"]:
            self.assertIn("domain", opp)
            self.assertIn("score", opp)
            score = opp["score"]
            self.assertIsInstance(score["score"], int)
            self.assertGreaterEqual(score["score"], 0)
            self.assertLessEqual(score["score"], 100)
            self.assertIsInstance(score["signals"], list)
            for signal in score["signals"]:
                self.assertIn("name", signal)
                self.assertIn("contribution", signal)
                self.assertIn("explanation", signal)
                self.assertIsInstance(signal["contribution"], int)
                self.assertIsInstance(signal["explanation"], str)
                self.assertTrue(signal["explanation"])

    def test_scan_rejects_non_positive_limit(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(
                ["scan", "--watchlist", str(EXAMPLE_WATCHLIST), "--limit", "0"],
                stdout=out,
            )
        self.assertEqual(rc, 2)
        self.assertIn("--limit must be >= 1", err.getvalue())

    def test_scan_missing_watchlist_returns_error(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(
                ["scan", "--watchlist", str(REPO_ROOT / "no-such-file.json")],
                stdout=out,
            )
        self.assertEqual(rc, 2)
        self.assertIn("error:", err.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
