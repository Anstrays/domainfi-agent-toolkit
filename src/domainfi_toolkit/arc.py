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
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


_RESOURCE_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_SAFE_MEMO_RE = re.compile(r"^[A-Za-z0-9 .,_:/()#@+-]{0,160}$")


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


def _validate_memo(memo: str | None) -> str | None:
    if memo is None:
        return None
    clean_memo = str(memo).strip()
    if not _SAFE_MEMO_RE.fullmatch(clean_memo):
        raise ValueError("memo may only contain safe printable characters and must be <= 160 chars")
    return clean_memo


def build_arc_builder_context() -> dict[str, Any]:
    """Return source-grounded Arc context for coding agents and docs.

    The shape deliberately separates public Arc facts from repo choices and
    unknown production work so an implementation agent cannot silently turn the
    local demo verifier into a real custody or settlement flow.
    """

    return {
        "official_arc_facts": {
            "network": "Arc Testnet",
            "chain_id": ARC_TESTNET.chain_id,
            "chain_id_hex": "0x4CEF52",
            "rpc_url": ARC_TESTNET.rpc_url,
            "explorer_url": ARC_TESTNET.explorer_url,
            "faucet_url": ARC_TESTNET.faucet_url,
            "native_gas_token": ARC_TESTNET.native_gas_token,
            "erc20_usdc_decimals": 6,
            "native_gas_decimals": 18,
            "cctp_domain": 26,
            "source_docs": [
                "https://docs.arc.network/llms.txt",
                "https://developers.circle.com/llms.txt",
            ],
        },
        "repo_implementation_choices": [
            "Expose a dependency-free demo-only x402-test proof for local paid-agent flows.",
            "Use integer microUSD prices so sub-cent API calls avoid float ambiguity.",
            "Keep example servers bound to localhost unless the operator explicitly changes --host.",
            "Return JSON payment intents, receipts, and unit economics for agent consumption.",
        ],
        "assumptions_and_unknowns": [
            "Production Circle Gateway/x402 verification is pluggable through CircleGatewayVerifier, but requires an operator-managed verifier endpoint and secrets.",
            "A production seller address, policy, rate limits, and receipt storage must be configured outside the demo.",
            "Human wallet approval remains mandatory for real Arc Testnet transactions.",
        ],
        "non_goals": [
            "No private keys, custody, autonomous spending, or mainnet fallback.",
            "No claims that x402-test is wire-compatible with production x402 settlement.",
        ],
    }


def build_arc_mcp_manifest() -> dict[str, Any]:
    """Return an MCP-style manifest for safe Arc paid-agent tools."""

    context = build_arc_builder_context()
    return {
        "name": "domainfi-arc-paid-agent-tools",
        "version": "0.1.0",
        "network": ARC_TESTNET.to_dict(),
        "tools": [
            {
                "name": "domainfi_arc_payment_intent",
                "description": "Build a machine-readable Arc Testnet / x402-style payment intent for a paid DomainFi resource.",
                "input_schema": {
                    "type": "object",
                    "required": ["resource", "amount_microusd", "pay_to"],
                    "properties": {
                        "resource": {"type": "string", "pattern": _RESOURCE_RE.pattern},
                        "amount_microusd": {"type": "integer", "minimum": 1},
                        "pay_to": {"type": "string", "pattern": _EVM_ADDRESS_RE.pattern},
                    },
                },
            },
            {
                "name": "domainfi_arc_payment_verify",
                "description": "Verify a local demo X-Payment proof and return an agent-readable receipt or rejection.",
                "input_schema": {
                    "type": "object",
                    "required": ["payment", "resource", "amount_microusd"],
                    "properties": {
                        "payment": {"type": "string"},
                        "resource": {"type": "string", "pattern": _RESOURCE_RE.pattern},
                        "amount_microusd": {"type": "integer", "minimum": 1},
                    },
                },
            },
            {
                "name": "domainfi_arc_gateway_verify",
                "description": "Verify an opaque production x402 proof with a configured Circle Gateway verifier endpoint.",
                "input_schema": {
                    "type": "object",
                    "required": ["payment", "gateway_url"],
                    "properties": {
                        "payment": {"type": "string"},
                        "gateway_url": {"type": "string"},
                        "gateway_api_key": {"type": "string"},
                        "resource": {"type": "string", "pattern": _RESOURCE_RE.pattern},
                        "amount_microusd": {"type": "integer", "minimum": 1},
                        "pay_to": {"type": "string", "pattern": _EVM_ADDRESS_RE.pattern},
                    },
                },
            },
            {
                "name": "domainfi_arc_paid_scan",
                "description": "Run the paid DomainFi discovery scan after payment verification succeeds.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "watchlist": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                },
            },
            {
                "name": "domainfi_arc_unit_economics",
                "description": "Estimate microUSD cost, price, and margin for pay-per-scan/alert/report products.",
                "input_schema": {
                    "type": "object",
                    "required": ["price_microusd"],
                    "properties": {
                        "provider_cost_microusd": {"type": "integer", "minimum": 0},
                        "infra_cost_microusd": {"type": "integer", "minimum": 0},
                        "settlement_cost_microusd": {"type": "integer", "minimum": 0},
                        "price_microusd": {"type": "integer", "minimum": 1},
                    },
                },
            },
        ],
        "production_replacement_boundary": (
            "Use domainfi_arc_gateway_verify / CircleGatewayVerifier with a trusted "
            "Circle Gateway/x402 verifier before accepting real payments."
        ),
        "safety": {
            "testnet_only": True,
            "human_wallet_approval_required": True,
            "no_private_keys": True,
            "no_autonomous_spending": True,
            "local_demo_proof_only": True,
        },
        "builder_context": context,
    }


def build_payment_intent(
    *,
    resource: str,
    amount_microusd: int,
    pay_to: str,
    provider_cost_microusd: int = 7_000,
    infra_cost_microusd: int = 2_000,
    settlement_cost_microusd: int = 1_000,
    memo: str | None = None,
) -> dict[str, Any]:
    """Build a complete local-demo Arc payment intent for agent clients."""

    clean_resource = _validate_resource(resource)
    amount = _validate_positive_int(amount_microusd, name="amount_microusd")
    economics = estimate_unit_economics(
        provider_cost_microusd=provider_cost_microusd,
        infra_cost_microusd=infra_cost_microusd,
        settlement_cost_microusd=settlement_cost_microusd,
        price_microusd=amount,
    )
    intent = {
        "kind": "arc_testnet_payment_intent",
        "status": "requires_payment",
        "network": ARC_TESTNET.to_dict(),
        "challenge": build_payment_required_response(resource=clean_resource, amount_microusd=amount, pay_to=pay_to),
        "local_demo_proof": f"x402-test:{clean_resource}:{amount}",
        "unit_economics": economics.to_dict(),
        "production_verifier": "Circle Gateway/x402 verification replaces the local x402-test proof parser.",
    }
    clean_memo = _validate_memo(memo)
    if clean_memo:
        intent["memo"] = clean_memo
    return intent


def build_gateway_verification_request(
    *,
    payment: str,
    resource: str,
    amount_microusd: int,
    pay_to: str,
) -> dict[str, Any]:
    """Build the explicit payload sent to a Circle Gateway/x402 verifier.

    This function does not sign or submit transactions. It standardizes the
    production verification seam so deployments can point at a trusted Gateway
    verifier/facilitator without changing the paid-agent business logic.
    """

    return {
        "payment": str(payment or "").strip(),
        "resource": _validate_resource(resource),
        "amount_microusd": _validate_positive_int(amount_microusd, name="amount_microusd"),
        "pay_to": _validate_evm_address(pay_to, name="pay_to"),
        "network": ARC_TESTNET.name,
        "chain_id": ARC_TESTNET.chain_id,
        "asset": "USDC",
        "asset_decimals": 6,
        "gateway_domain": 26,
    }


class CircleGatewayVerifier:
    """Production-verifier seam for Circle Gateway/x402 payment proofs.

    The toolkit never stores keys or performs autonomous settlement. This class
    POSTs an opaque payment proof to a configured verifier endpoint and returns
    a normalized receipt/rejection. Operators are expected to provide the
    endpoint and secret through environment variables or a deployment secret
    manager.
    """

    def __init__(self, base_url: str, *, api_key: str | None = None, timeout_seconds: int = 20) -> None:
        clean_url = str(base_url or "").strip().rstrip("/") + "/"
        parsed = urlparse(clean_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Gateway verifier URL must be an http(s) URL")
        if isinstance(timeout_seconds, bool) or int(timeout_seconds) <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self.base_url = clean_url
        self.api_key = str(api_key).strip() if api_key else None
        self.timeout_seconds = int(timeout_seconds)

    def verify(self, *, payment: str, resource: str, amount_microusd: int, pay_to: str) -> dict[str, Any]:
        payload = build_gateway_verification_request(
            payment=payment,
            resource=resource,
            amount_microusd=amount_microusd,
            pay_to=pay_to,
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "domainfi-agent-toolkit/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            urljoin(self.base_url, "x402/verify"),
            data=json.dumps(payload, sort_keys=True).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            gateway_payload = json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - normalize and redact before returning to agents.
            return {
                "paid": False,
                "status": "rejected",
                "reason": self._redact(str(exc)),
                "production_verifier": "circle_gateway",
                "request": {key: value for key, value in payload.items() if key != "payment"},
            }
        paid = bool(gateway_payload.get("paid") or gateway_payload.get("status") == "accepted")
        return {
            "paid": paid,
            "status": "accepted" if paid else "rejected",
            "production_verifier": "circle_gateway",
            "gateway_response": gateway_payload,
            "network": ARC_TESTNET.to_dict(),
        }

    def _redact(self, text: str) -> str:
        if self.api_key:
            return text.replace(self.api_key, "[REDACTED]")
        return text


def verify_payment_intent(header: str | None, *, resource: str, amount_microusd: int) -> dict[str, Any]:
    """Verify a local-demo payment proof and return a stable receipt shape."""

    clean_resource = _validate_resource(resource)
    amount = _validate_positive_int(amount_microusd, name="amount_microusd")
    try:
        payment = parse_x402_payment_header(header or "")
    except (TypeError, ValueError) as exc:
        return {
            "paid": False,
            "status": "rejected",
            "reason": str(exc),
            "resource": clean_resource,
            "required_amount_microusd": amount,
            "network": ARC_TESTNET.to_dict(),
        }
    if payment.resource != clean_resource:
        return {
            "paid": False,
            "status": "rejected",
            "reason": "payment resource does not match requested resource",
            "resource": clean_resource,
            "required_amount_microusd": amount,
            "received": payment.to_dict(),
            "network": ARC_TESTNET.to_dict(),
        }
    if payment.amount_microusd < amount:
        return {
            "paid": False,
            "status": "rejected",
            "reason": "payment amount is below required amount",
            "resource": clean_resource,
            "required_amount_microusd": amount,
            "received": payment.to_dict(),
            "network": ARC_TESTNET.to_dict(),
        }
    return {
        "paid": True,
        "status": "accepted",
        "resource": clean_resource,
        "required_amount_microusd": amount,
        "received": payment.to_dict(),
        "network": ARC_TESTNET.to_dict(),
        "local_demo_only": True,
        "production_verifier": "Use Circle Gateway/x402 receipt verification before real settlement.",
    }
