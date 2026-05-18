"""DomainFi Agent Toolkit — Phase 2 prototype.

A dependency-free Python package that demonstrates the agent layer
described in docs/ARCHITECTURE.md:

    provider -> scoring -> watchlist filter -> notification

The current build ships with a ``MockDomainProvider`` so the pipeline
can be exercised end-to-end without any Doma API access. Once Doma
SDK / API endpoints are available, a real provider can be plugged in
behind the same ``DomainProvider`` interface.
"""

from .agent import DiscoveryAgent, ScanResult
from .arc import (
    ARC_TESTNET,
    ArcNetworkConfig,
    UnitEconomics,
    X402Payment,
    build_paid_discovery_payload,
    build_payment_required_response,
    estimate_unit_economics,
    parse_x402_payment_header,
    verify_x402_payment_header,
)
from .models import (
    Alert,
    Domain,
    Listing,
    Opportunity,
    ScoreResult,
    Signal,
    Watchlist,
)
from .notifiers import ConsoleNotifier, DiscordNotifier, MultiNotifier, Notifier, TelegramNotifier
from .providers import DomainProvider, MockDomainProvider
from .scoring import explain, load_weights, reset_weights, score_domain
from .watchlist import load_watchlists

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Agent
    "DiscoveryAgent",
    "ScanResult",
    # Arc paid-agent MVP
    "ARC_TESTNET",
    "ArcNetworkConfig",
    "UnitEconomics",
    "X402Payment",
    "build_paid_discovery_payload",
    "build_payment_required_response",
    "estimate_unit_economics",
    "parse_x402_payment_header",
    "verify_x402_payment_header",
    # Models
    "Alert",
    "Domain",
    "Listing",
    "Opportunity",
    "ScoreResult",
    "Signal",
    "Watchlist",
    # Providers
    "DomainProvider",
    "MockDomainProvider",
    # Scoring
    "explain",
    "load_weights",
    "reset_weights",
    "score_domain",
    # Watchlists
    "load_watchlists",
    # Notifiers
    "ConsoleNotifier",
    "DiscordNotifier",
    "MultiNotifier",
    "Notifier",
    "TelegramNotifier",
]
