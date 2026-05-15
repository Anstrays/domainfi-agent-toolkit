"""DomainFi Agent Toolkit — Phase 2 prototype.

A dependency-free Python package that demonstrates the agent layer
described in docs/ARCHITECTURE.md:

    provider -> scoring -> watchlist filter -> notification

The current build ships with a ``MockDomainProvider`` so the pipeline
can be exercised end-to-end without any Doma API access. Once Doma
SDK / API endpoints are available, a real provider can be plugged in
behind the same ``DomainProvider`` interface.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
