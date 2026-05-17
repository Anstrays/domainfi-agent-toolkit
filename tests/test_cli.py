from __future__ import annotations

import contextlib
import io
import json
import tempfile
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

    def test_scan_sort_by_price_and_explain(self) -> None:
        out = io.StringIO()
        rc = main(
            [
                "scan",
                "--watchlist",
                str(EXAMPLE_WATCHLIST),
                "--limit",
                "2",
                "--sort-by",
                "price",
                "--explain",
                "--no-color",
            ],
            stdout=out,
        )
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("explain:", text)
        self.assertIn("Found 2 domain opportunities", text)

    def test_scan_min_score_override_and_output_file(self) -> None:
        out = io.StringIO()
        output_path = REPO_ROOT / ".tmp-scan-output.json"
        try:
            rc = main(
                [
                    "scan",
                    "--watchlist",
                    str(EXAMPLE_WATCHLIST),
                    "--min-score",
                    "90",
                    "--output",
                    str(output_path),
                    "--json",
                ],
                stdout=out,
            )
            self.assertEqual(rc, 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload, json.loads(out.getvalue()))
            for opp in payload["opportunities"]:
                self.assertGreaterEqual(opp["score"]["score"], 90)
        finally:
            output_path.unlink(missing_ok=True)

    def test_scan_min_score_override_can_lower_watchlist_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            watchlist = Path(tmp) / "watchlist.json"
            watchlist.write_text(
                json.dumps({"name": "strict", "keywords": ["ai"], "min_score": 90}),
                encoding="utf-8",
            )
            out = io.StringIO()
            rc = main(["scan", "--watchlist", str(watchlist), "--min-score", "0", "--json"], stdout=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertGreater(payload["count"], 0)

    def test_scan_rejects_malformed_weights_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            weights = Path(tmp) / "weights.json"
            weights.write_text(
                json.dumps(
                    {
                        "brandability": None,
                        "keyword": 30,
                        "category": 15,
                        "tld": 10,
                        "price": 15,
                        "expiry": 30,
                    }
                ),
                encoding="utf-8",
            )
            out = io.StringIO()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = main(["scan", "--watchlist", str(EXAMPLE_WATCHLIST), "--weights", str(weights)], stdout=out)
        self.assertEqual(rc, 2)
        self.assertIn("failed to load weights", err.getvalue())

    def test_scan_output_write_error_is_clean(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(
                [
                    "scan",
                    "--watchlist",
                    str(EXAMPLE_WATCHLIST),
                    "--output",
                    str(REPO_ROOT / "no-such-dir" / "scan.json"),
                ],
                stdout=out,
            )
        self.assertEqual(rc, 2)
        self.assertIn("failed to write output", err.getvalue())

    def test_scan_rejects_invalid_min_score(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(
                ["scan", "--watchlist", str(EXAMPLE_WATCHLIST), "--min-score", "101"],
                stdout=out,
            )
        self.assertEqual(rc, 2)
        self.assertIn("--min-score must be in 0..100", err.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
