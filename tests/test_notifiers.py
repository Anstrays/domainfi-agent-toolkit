from __future__ import annotations

import io
import os
import time
import urllib.error
import unittest
from datetime import date
from unittest.mock import patch

from domainfi_toolkit.models import Alert, Domain, Listing, Opportunity, ScoreResult, Signal
from domainfi_toolkit.notifiers import (
    _http_post,
    ConsoleNotifier,
    DiscordNotifier,
    MultiNotifier,
    TelegramNotifier,
)


def _make_opp(name: str = "example.com", price: float = 1000, score: int = 55) -> Opportunity:
    domain = Domain.from_name(name, category="ai-tools")
    listing = Listing(
        domain=domain.name,
        price_usd=price,
        marketplace="mock",
        listed_at="2026-05-17T00:00:00Z",
    )
    result = ScoreResult(
        domain=domain.name,
        score=score,
        signals=(Signal("keyword", ["example"], 20, "keyword matched"),),
    )
    return Opportunity(domain=domain, listing=listing, score=result, matched_watchlist="demo")


class TestConsoleNotifier(unittest.TestCase):
    def test_sends_alerts_to_custom_stream(self) -> None:
        stream = io.StringIO()
        notifier = ConsoleNotifier(stream=stream)
        count = notifier.send([Alert(title="title", body="body", domain="example.com")])
        self.assertEqual(count, 1)
        self.assertIn("[INFO] example.com title", stream.getvalue())
        self.assertIn("body", stream.getvalue())

    def test_sends_opportunities_to_custom_stream(self) -> None:
        stream = io.StringIO()
        notifier = ConsoleNotifier(stream=stream)
        count = notifier.send([_make_opp()])
        self.assertEqual(count, 1)
        self.assertIn("example.com", stream.getvalue())
        self.assertIn("score=55/100", stream.getvalue())

    def test_empty_list_sends_nothing(self) -> None:
        stream = io.StringIO()
        count = ConsoleNotifier(stream=stream).send([])
        self.assertEqual(count, 0)
        self.assertEqual(stream.getvalue(), "")

    def test_cooldown_suppresses_second_call(self) -> None:
        stream = io.StringIO()
        notifier = ConsoleNotifier(stream=stream, cooldown_seconds=60)
        self.assertEqual(notifier.send([_make_opp()]), 1)
        self.assertEqual(notifier.send([_make_opp("second.com")]), 0)
        self.assertNotIn("second.com", stream.getvalue())

    def test_cooldown_allows_first_send_even_when_monotonic_clock_is_low(self) -> None:
        stream = io.StringIO()
        notifier = ConsoleNotifier(stream=stream, cooldown_seconds=300)

        with patch("domainfi_toolkit.notifiers.time.monotonic", return_value=1.0):
            self.assertEqual(notifier.send([_make_opp()]), 1)

        self.assertIn("example.com", stream.getvalue())


class TestTelegramNotifier(unittest.TestCase):
    def test_dry_run_without_credentials(self) -> None:
        stream = io.StringIO()
        notifier = TelegramNotifier(cooldown_seconds=0, stream=stream)
        self.assertEqual(notifier.send([_make_opp()]), 1)
        self.assertIn("[telegram-stub] would send", stream.getvalue())

    def test_raises_with_only_token(self) -> None:
        notifier = TelegramNotifier(bot_token="abc", cooldown_seconds=0)
        with self.assertRaises(ValueError):
            notifier.send([_make_opp()])

    def test_calls_http_post_with_credentials(self) -> None:
        notifier = TelegramNotifier(bot_token="tok", chat_id="123", cooldown_seconds=0)
        with patch("domainfi_toolkit.notifiers._http_post") as mock_post:
            self.assertEqual(notifier.send([_make_opp()]), 1)
        mock_post.assert_called_once()
        url, payload = mock_post.call_args.args
        self.assertIn("tok", url)
        self.assertEqual(payload["chat_id"], "123")
        self.assertIn("example.com", payload["text"])

    def test_from_env_reads_env_vars(self) -> None:
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}):
            notifier = TelegramNotifier.from_env(cooldown_seconds=0)
        with patch("domainfi_toolkit.notifiers._http_post") as mock_post:
            notifier.send([_make_opp()])
        self.assertIn("t", mock_post.call_args.args[0])


class TestDiscordNotifier(unittest.TestCase):
    def test_dry_run_without_webhook(self) -> None:
        stream = io.StringIO()
        notifier = DiscordNotifier(cooldown_seconds=0, stream=stream)
        self.assertEqual(notifier.send([_make_opp()]), 1)
        self.assertIn("[discord-stub] would send", stream.getvalue())

    def test_calls_http_post_with_webhook(self) -> None:
        notifier = DiscordNotifier(webhook_url="https://discord.test/webhook", cooldown_seconds=0)
        with patch("domainfi_toolkit.notifiers._http_post") as mock_post:
            self.assertEqual(notifier.send([_make_opp()]), 1)
        url, payload = mock_post.call_args.args
        self.assertEqual(url, "https://discord.test/webhook")
        self.assertEqual(payload["embeds"][0]["fields"][0]["name"].startswith("example.com"), True)


class TestHttpPost(unittest.TestCase):
    def test_error_message_redacts_secret_url(self) -> None:
        class Response:
            status = 500

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        secret_url = "https://api.telegram.org/botsecret-token/sendMessage"
        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaises(urllib.error.URLError) as ctx:
                _http_post(secret_url, {"ok": False})
        message = str(ctx.exception)
        self.assertIn("notification endpoint", message)
        self.assertNotIn("secret-token", message)
        self.assertNotIn(secret_url, message)


class TestMultiNotifier(unittest.TestCase):
    def test_fans_out_to_all_children(self) -> None:
        one = ConsoleNotifier(stream=io.StringIO())
        two = ConsoleNotifier(stream=io.StringIO())
        multi = MultiNotifier([one, two])
        self.assertEqual(multi.send([_make_opp()]), 2)
        self.assertEqual(multi.errors, [])

    def test_continues_after_child_failure(self) -> None:
        class Broken(ConsoleNotifier):
            def _deliver(self, items):
                raise RuntimeError("boom")

        good = ConsoleNotifier(stream=io.StringIO())
        multi = MultiNotifier([Broken(stream=io.StringIO()), good])
        self.assertEqual(multi.send([_make_opp()]), 1)
        self.assertEqual(len(multi.errors), 1)


class TestCooldown(unittest.TestCase):
    def test_cooldown_expires(self) -> None:
        stream = io.StringIO()
        notifier = ConsoleNotifier(stream=stream, cooldown_seconds=0.001)
        self.assertEqual(notifier.send([_make_opp()]), 1)
        time.sleep(0.002)
        self.assertEqual(notifier.send([_make_opp("again.com")]), 1)
        self.assertIn("again.com", stream.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
