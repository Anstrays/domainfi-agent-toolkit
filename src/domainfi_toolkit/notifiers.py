"""Notification adapters.

Only the console notifier is implemented today. ``TelegramNotifier``
and ``DiscordNotifier`` are intentionally no-op stubs that document
the interface and refuse to send anything until they are wired up
with real credentials and an explicit user opt-in. This matches the
"no automated state changes without confirmation" stance from
SECURITY.md and docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import sys
from typing import Iterable, Protocol, TextIO

from .models import Alert


class Notifier(Protocol):
    def send(self, alerts: Iterable[Alert]) -> int: ...


class ConsoleNotifier:
    """Prints alerts to stdout (or any text stream)."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def send(self, alerts: Iterable[Alert]) -> int:
        count = 0
        for alert in alerts:
            count += 1
            prefix = f"[{alert.severity.upper()}]"
            domain_part = f" {alert.domain}" if alert.domain else ""
            print(f"{prefix}{domain_part} {alert.title}", file=self._stream)
            if alert.body:
                for line in alert.body.splitlines():
                    print(f"  {line}", file=self._stream)
        return count


class _DryRunNotifier:
    """Base class for adapters that are not wired to real services yet."""

    channel: str = "dry-run"

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def send(self, alerts: Iterable[Alert]) -> int:
        count = 0
        for alert in alerts:
            count += 1
            print(
                f"[{self.channel}] would send: {alert.title}"
                + (f" (domain={alert.domain})" if alert.domain else ""),
                file=self._stream,
            )
        return count


class TelegramNotifier(_DryRunNotifier):
    """Stub Telegram adapter. Does not perform any network I/O.

    A real implementation should:
      * read the bot token from an environment variable,
      * confirm the target chat id with the user,
      * apply rate limits and dedupe alerts,
      * never include secrets or wallet addresses in messages by default.
    """

    channel = "telegram-stub"


class DiscordNotifier(_DryRunNotifier):
    """Stub Discord adapter. Does not perform any network I/O.

    A real implementation should use a webhook URL from an environment
    variable and apply the same dedupe/rate-limit rules as Telegram.
    """

    channel = "discord-stub"
