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
        payload = json.loads(out.getvalue())
        self.assertIn("opportunities", payload)
        self.assertLessEqual(len(payload["opportunities"]), 3)
        if payload["opportunities"]:
            opp = payload["opportunities"][0]
            self.assertIn("score", opp)
            self.assertIn("signals", opp["score"])

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
