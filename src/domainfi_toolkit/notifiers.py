"""Notification adapters for alerts and opportunities.

The toolkit remains dependency-free and safe-by-default: console output is
local-only, while Telegram and Discord require explicit credentials before
performing any network I/O.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, Protocol, TextIO, Union

from .models import Alert, Opportunity

NotificationItem = Union[Alert, Opportunity]


class Notifier(Protocol):
    """Backward-compatible notifier protocol."""

    def send(self, items: Iterable[NotificationItem]) -> int: ...


@dataclass
class _Cooldown:
    """Allow at most one send per ``seconds`` window."""

    seconds: float
    _last_sent: float | None = field(default=None, init=False, repr=False)

    def ready(self) -> bool:
        if self._last_sent is None:
            return True
        return (time.monotonic() - self._last_sent) >= self.seconds

    def mark(self) -> None:
        self._last_sent = time.monotonic()


class BaseNotifier(ABC):
    """Base class that adds shared cooldown handling."""

    def __init__(self, cooldown_seconds: float = 0.0) -> None:
        self._cooldown = _Cooldown(cooldown_seconds)

    def send(self, items: Iterable[NotificationItem]) -> int:
        batch = list(items)
        if not batch:
            return 0
        if not self._cooldown.ready():
            return 0
        delivered = self._deliver(batch)
        self._cooldown.mark()
        return delivered

    @abstractmethod
    def _deliver(self, items: list[NotificationItem]) -> int: ...


class ConsoleNotifier(BaseNotifier):
    """Print notifications to stdout or any text stream."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        out: TextIO | None = None,
        cooldown_seconds: float = 0.0,
    ) -> None:
        super().__init__(cooldown_seconds)
        self._stream = stream or out or sys.stdout

    def _deliver(self, items: list[NotificationItem]) -> int:
        count = 0
        for item in items:
            count += 1
            if isinstance(item, Alert):
                prefix = f"[{item.severity.upper()}]"
                domain_part = f" {item.domain}" if item.domain else ""
                print(f"{prefix}{domain_part} {item.title}", file=self._stream)
                if item.body:
                    for line in item.body.splitlines():
                        print(f"    {line}", file=self._stream)
                continue

            listing = item.listing
            price_part = (
                f" at ${listing.price_usd:,.0f} on {listing.marketplace}"
                if listing
                else " with no active listing"
            )
            print(
                f"[WATCHLIST] {item.domain.name} score={item.score.score}/100{price_part}",
                file=self._stream,
            )
        return count


def _http_post(url: str, payload: dict) -> None:
    """POST JSON to a webhook endpoint."""

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status not in (200, 201, 204):
            raise urllib.error.URLError(f"Unexpected HTTP {resp.status} from notification endpoint")


def _item_title(item: NotificationItem) -> str:
    if isinstance(item, Alert):
        domain = f" {item.domain}" if item.domain else ""
        return f"{item.title}{domain}"
    listing = item.listing
    price = f"${listing.price_usd:,.0f}" if listing else "no listing"
    return f"{item.domain.name} — score {item.score.score}/100 — {price}"


def _item_body(item: NotificationItem) -> str:
    if isinstance(item, Alert):
        return item.body
    signals = sorted(item.score.signals, key=lambda s: s.contribution, reverse=True)[:3]
    reasons = "; ".join(s.explanation for s in signals if s.contribution)
    return reasons or "baseline match"


class TelegramNotifier(BaseNotifier):
    """Send notifications through Telegram Bot API.

    No network I/O occurs until both ``bot_token`` and ``chat_id`` are set and
    ``send`` is called explicitly.
    """

    _API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        cooldown_seconds: float = 300.0,
        stream: TextIO | None = None,
    ) -> None:
        super().__init__(cooldown_seconds)
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._stream = stream or sys.stdout

    def _deliver(self, items: list[NotificationItem]) -> int:
        if not self._bot_token and not self._chat_id:
            for item in items:
                print(f"[telegram-stub] would send: {_item_title(item)}", file=self._stream)
            return len(items)
        if not self._bot_token or not self._chat_id:
            raise ValueError(
                "TelegramNotifier requires both bot_token and chat_id. "
                "Set them explicitly or via TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID."
            )
        lines = [f"🔔 {len(items)} DomainFi notification(s)"]
        for item in items:
            lines.append(f"• {_item_title(item)}")
            body = _item_body(item)
            if body:
                lines.append(f"  {body}")
        _http_post(
            self._API_URL.format(token=self._bot_token),
            {"chat_id": self._chat_id, "text": "\n".join(lines)},
        )
        return len(items)

    @classmethod
    def from_env(cls, cooldown_seconds: float = 300.0) -> "TelegramNotifier":
        return cls(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            cooldown_seconds=cooldown_seconds,
        )


class DiscordNotifier(BaseNotifier):
    """Post notifications to a Discord incoming webhook."""

    def __init__(
        self,
        webhook_url: str | None = None,
        cooldown_seconds: float = 300.0,
        stream: TextIO | None = None,
    ) -> None:
        super().__init__(cooldown_seconds)
        self._webhook_url = webhook_url
        self._stream = stream or sys.stdout

    def _deliver(self, items: list[NotificationItem]) -> int:
        if not self._webhook_url:
            for item in items:
                print(f"[discord-stub] would send: {_item_title(item)}", file=self._stream)
            return len(items)
        fields = [
            {
                "name": _item_title(item),
                "value": _item_body(item) or "No details",
                "inline": False,
            }
            for item in items
        ]
        payload = {
            "embeds": [
                {
                    "title": f"🔔 {len(items)} DomainFi notification(s)",
                    "color": 0x5865F2,
                    "fields": fields,
                }
            ]
        }
        _http_post(self._webhook_url, payload)
        return len(items)

    @classmethod
    def from_env(cls, cooldown_seconds: float = 300.0) -> "DiscordNotifier":
        return cls(
            webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
            cooldown_seconds=cooldown_seconds,
        )


class MultiNotifier(BaseNotifier):
    """Fan out to child notifiers, collecting child errors."""

    def __init__(self, notifiers: list[BaseNotifier]) -> None:
        super().__init__(cooldown_seconds=0.0)
        self._notifiers = list(notifiers)
        self.errors: list[tuple[BaseNotifier, Exception]] = []

    def _deliver(self, items: list[NotificationItem]) -> int:
        self.errors.clear()
        delivered = 0
        for notifier in self._notifiers:
            try:
                delivered += notifier.send(items)
            except Exception as exc:  # pragma: no cover - exact child failures vary
                self.errors.append((notifier, exc))
        return delivered
