"""Arc/Circle payment helpers for the DomainFi paid-agent MVP.

The module intentionally stays dependency-free and does not submit real
transactions. It models the product surface builders need before wiring a
production Gateway/x402 implementation:

- Arc Testnet network constants
- HTTP 402/x402 challenge payloads for pay-per-request APIs
- deterministic local demo payment header parsing
- unit economics for tiny USDC-priced agent calls
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


_RESOURCE_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


@dataclass(frozen=True)
class ArcNetworkConfig:
    """Connection details for Arc Testnet."""

    name: str
    chain_id: int
    rpc_url: str
    explorer_url: str
    faucet_url: str
    native_gas_token: str = "USDC"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ARC_TESTNET = ArcNetworkConfig(
    name="arc-testnet",
    chain_id=5042002,
    rpc_url="https://rpc.testnet.arc.network",
    explorer_url="https://testnet.arcscan.app",
    faucet_url="https://faucet.circle.com",
)


@dataclass(frozen=True)
class X402Payment:
    """A local-demo representation of an x402 payment proof."""

    scheme: str
    resource: str
    amount_microusd: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UnitEconomics:
    """Per-request economics in micro-dollars.

    ``microusd`` means one millionth of a USD. This matches the practical
    mental model for Circle Gateway nanopayments, where sub-cent prices are
    valid and should not be represented with imprecise floats.
    """

    provider_cost_microusd: int
    infra_cost_microusd: int
    settlement_cost_microusd: int
    price_microusd: int

    @property
    def total_cost_microusd(self) -> int:
        return self.provider_cost_microusd + self.infra_cost_microusd + self.settlement_cost_microusd

    @property
    def gross_margin_microusd(self) -> int:
        return self.price_microusd - self.total_cost_microusd

    @property
    def gross_margin_percent(self) -> float:
        if self.price_microusd == 0:
            return 0.0
        return round((self.gross_margin_microusd / self.price_microusd) * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["total_cost_microusd"] = self.total_cost_microusd
        payload["gross_margin_microusd"] = self.gross_margin_microusd
        payload["gross_margin_percent"] = self.gross_margin_percent
        payload["unit"] = "microUSD"
        return payload


def _validate_non_negative_int(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _validate_positive_int(value: int, *, name: str) -> int:
    _validate_non_negative_int(value, name=name)
    if value == 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _validate_resource(resource: str) -> str:
    clean_resource = str(resource).strip()
    if not clean_resource:
        raise ValueError("resource is required")
    if not _RESOURCE_RE.fullmatch(clean_resource):
        raise ValueError("resource may only contain letters, digits, '.', '_', '/', and '-'")
    return clean_resource


def _validate_evm_address(address: str, *, name: str) -> str:
    clean_address = str(address).strip()
    if not clean_address:
        raise ValueError(f"{name} is required")
    if not _EVM_ADDRESS_RE.fullmatch(clean_address):
        raise ValueError(f"{name} must be a 0x-prefixed 20-byte EVM address")
    return clean_address


def build_payment_required_response(*, resource: str, amount_microusd: int, pay_to: str) -> dict[str, Any]:
    """Build a 402 response body for a paid DomainFi API endpoint.

    This mirrors the x402 seller-side shape: the protected API tells the
    agent what network, asset, amount, and destination are accepted. A real
    Gateway integration would verify the returned payment proof with Circle;
    the local MVP uses ``x402-test:<resource>:<amount_microusd>`` so the
    workflow can be tested without keys or custody.
    """

    amount = _validate_positive_int(amount_microusd, name="amount_microusd")
    clean_resource = _validate_resource(resource)
    clean_pay_to = _validate_evm_address(pay_to, name="pay_to")

    return {
        "status": 402,
        "error": "payment_required",
        "resource": clean_resource,
        "accepts": [
            {
                "scheme": "x402-test",
                "network": ARC_TESTNET.name,
                "chain_id": ARC_TESTNET.chain_id,
                "asset": "USDC",
                "amount_microusd": amount,
                "pay_to": clean_pay_to,
            }
        ],
        "instructions": (
            "Send the request again with header "
            f"X-Payment: x402-test:{clean_resource}:{amount}"
        ),
    }


def parse_x402_payment_header(header: str) -> X402Payment:
    """Parse the local-demo x402 payment proof header."""

    parts = str(header).strip().split(":")
    if len(parts) != 3 or parts[0] != "x402-test":
        raise ValueError("unsupported x402 payment header")
    resource = _validate_resource(parts[1])
    try:
        amount = int(parts[2])
    except ValueError as exc:
        raise ValueError("x402 amount must be an integer") from exc
    _validate_positive_int(amount, name="amount_microusd")
    return X402Payment(scheme=parts[0], resource=resource, amount_microusd=amount)


def verify_x402_payment_header(header: str | None, *, resource: str, amount_microusd: int) -> bool:
    """Return True when a local-demo x402 header pays for the resource."""

    if not header:
        return False
    try:
        payment = parse_x402_payment_header(header)
    except (TypeError, ValueError):
        return False
    return payment.resource == resource and payment.amount_microusd >= amount_microusd


def estimate_unit_economics(
    *,
    provider_cost_microusd: int,
    infra_cost_microusd: int,
    settlement_cost_microusd: int,
    price_microusd: int,
) -> UnitEconomics:
    """Create a validated per-request unit-economics estimate."""

    return UnitEconomics(
        provider_cost_microusd=_validate_non_negative_int(provider_cost_microusd, name="provider_cost_microusd"),
        infra_cost_microusd=_validate_non_negative_int(infra_cost_microusd, name="infra_cost_microusd"),
        settlement_cost_microusd=_validate_non_negative_int(settlement_cost_microusd, name="settlement_cost_microusd"),
        price_microusd=_validate_positive_int(price_microusd, name="price_microusd"),
    )


def build_paid_discovery_payload(
    *,
    request_id: str,
    watchlist: str,
    paid: bool,
    amount_microusd: int,
) -> dict[str, Any]:
    """Return a compact response payload for the paid discovery demo."""

    amount = _validate_positive_int(amount_microusd, name="amount_microusd")
    return {
        "request_id": str(request_id),
        "watchlist": str(watchlist),
        "payment": {
            "paid": bool(paid),
            "network": ARC_TESTNET.name,
            "chain_id": ARC_TESTNET.chain_id,
            "asset": "USDC",
            "amount_microusd": amount,
        },
        "why_arc": [
            "USDC is the native gas token, so users can reason about API cost and gas in dollars.",
            "Sub-second deterministic finality fits pay-per-alert and pay-per-scan agent loops.",
            "Gateway/x402 can turn DomainFi intelligence into a paid API without subscriptions first.",
        ],
    }
