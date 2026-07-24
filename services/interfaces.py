from typing import Any, Dict, List, Optional
"""
services/interfaces.py

Enterprise interfaces for the MIP PRO Market Intelligence Platform.

This module defines the canonical repository contract for accessing
live market data. Business services should depend on these interfaces
rather than concrete implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IMarketRepository(ABC):
    """
    Canonical interface for the Market Repository.

    Every repository implementation must expose a consistent API,
    regardless of the underlying market data provider.
    """

    @abstractmethod
    def refresh(self) -> Dict[str, Dict[str, Any]]:
        """
        Refresh live market data from the provider.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            Dictionary keyed by symbol containing normalized quotes.
        """
        raise NotImplementedError

    @abstractmethod
    def get_all_quotes(self) -> Dict[str, Dict[str, Any]]:
        """
        Return all cached normalized quotes.
        """
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Return a normalized quote for a single symbol.
        """
        raise NotImplementedError

    @abstractmethod
    def get_market_status(self) -> Dict[str, Any]:
        """
        Return market/session status.
        """
        raise NotImplementedError

    @abstractmethod
    def get_provider_health(self) -> Dict[str, Any]:
        """
        Return provider health information.
        """
        raise NotImplementedError

class ISignalRepository(ABC):
    """
    Contract for storing and retrieving finalized trading signals.

    The repository is the authoritative source for downstream consumers
    such as the dashboard, portfolio adviser, Telegram alerts, learning
    engine, reports, and shadow portfolio.
    """

    @abstractmethod
    def save_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save or update the finalized signal for one security.

        The supplied dictionary should contain at least:
        - symbol
        - decision or signal
        - score or committee_score
        """

    @abstractmethod
    def save_signals(
        self,
        signals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Save or update multiple finalized signals."""

    @abstractmethod
    def get_signal(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the latest finalized signal for one symbol."""

    @abstractmethod
    def get_all_signals(self) -> List[Dict[str, Any]]:
        """Return the latest finalized signal for every symbol."""

    @abstractmethod
    def get_signals_by_decision(
        self,
        decision: str,
    ) -> List[Dict[str, Any]]:
        """Return signals matching a decision such as BUY or HOLD."""

    @abstractmethod
    def get_top_signals(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return the highest-ranked finalized signals."""

    @abstractmethod
    def clear(self) -> None:
        """Clear the repository's current in-memory signal state."""

