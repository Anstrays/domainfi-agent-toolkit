from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from domainfi_toolkit.cli import main


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class DomaProviderCliTests(unittest.TestCase):
    def test_scan_can_use_doma_http_provider(self) -> None:
        def fake_urlopen(request, timeout=0):
            if request.full_url.endswith("/domains"):
                return _FakeResponse({"domains": [{"name": "ArcSignal.com", "category": "ai"}]})
            if request.full_url.endswith("/listings"):
                return _FakeResponse(
                    {
                        "listings": [
                            {
                                "domain": "ArcSignal.com",
                                "price_usd": 99,
                                "marketplace": "doma",
                                "listed_at": "2026-01-01T00:00:00Z",
                            }
                        ]
                    }
                )
            raise AssertionError(request.full_url)

        watchlist = json.dumps({"name": "arc", "keywords": ["arc"], "max_price_usd": 200})
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.json"
            path.write_text(watchlist, encoding="utf-8")
            out = io.StringIO()
            with patch("domainfi_toolkit.providers.urlopen", fake_urlopen):
                rc = main(
                    [
                        "scan",
                        "--watchlist",
                        str(path),
                        "--provider",
                        "doma-http",
                        "--doma-api-url",
                        "https://api.example.test/v1",
                        "--doma-api-key",
                        "testtok",
                        "--json",
                    ],
                    stdout=out,
                )

        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["provider"], "doma-http")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["opportunities"][0]["domain"]["name"], "arcsignal.com")

    def test_doma_http_provider_requires_url(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(["scan", "--watchlist", "missing.json", "--provider", "doma-http"], stdout=out)
        self.assertEqual(rc, 2)
        self.assertIn("--doma-api-url", err.getvalue())


if __name__ == "__main__":
    unittest.main()
