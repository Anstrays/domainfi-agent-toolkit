"""DomainFi Agent Toolkit — Phase 2 prototype.

A dependency-free Python package that demonstrates the agent layer
described in docs/ARCHITECTURE.md:

    provider -> scoring -> watchlist filter -> notification

The current build ships with a ``MockDomainProvider`` so the pipeline
can be exercised end-to-end without any Doma API access. Once Doma
SDK / API endpoints are available, a real provider can be plugged in
behind the same ``DomainProvider`` interface.
"""

from .agent import DiscoveryAgent
from .models import (
    Alert,
    Domain,
    Listing,
    Opportunity,
    ScoreResult,
    Signal,
    Watchlist,
)
from .notifiers import ConsoleNotifier, DiscordNotifier, Notifier, TelegramNotifier
from .providers import DomainProvider, MockDomainProvider
from .scoring import score_domain
from .watchlist import load_watchlists

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Agent
    "DiscoveryAgent",
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
    "score_domain",
    # Watchlists
    "load_watchlists",
    # Notifiers
    "ConsoleNotifier",
    "DiscordNotifier",
    "Notifier",
    "TelegramNotifier",
]
