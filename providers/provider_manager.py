from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Protocol


logger = logging.getLogger(__name__)


class MarketDataProvider(Protocol):
    """Required interface for every market-data provider."""

    name: str

    def fetch_quotes(self) -> Dict[str, Dict[str, Any]]:
        ...

    def fetch_market_status(self) -> Dict[str, Any]:
        ...

    def health_check(self) -> bool:
        ...


class ProviderManager:
    """
    Controls the primary market-data provider and optional fallback providers.

    The first healthy provider that returns valid data is used.
    """

    def __init__(
        self,
        primary_provider: MarketDataProvider,
        fallback_providers: Optional[List[MarketDataProvider]] = None,
    ) -> None:
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers or []
        self.active_provider: Optional[str] = None
        self.last_error: Optional[str] = None

    def _providers(self) -> List[MarketDataProvider]:
        return [self.primary_provider, *self.fallback_providers]

    @staticmethod
    def _valid_quotes(data: Any) -> bool:
        return isinstance(data, dict) and len(data) > 0

    def get_live_quotes(self) -> Dict[str, Dict[str, Any]]:
        errors: List[str] = []

        for provider in self._providers():
            provider_name = getattr(provider, "name", provider.__class__.__name__)

            try:
                if not provider.health_check():
                    errors.append(f"{provider_name}: health check failed")
                    continue

                quotes = provider.fetch_quotes()

                if not self._valid_quotes(quotes):
                    errors.append(f"{provider_name}: empty or invalid quote response")
                    continue

                self.active_provider = provider_name
                self.last_error = None

                logger.info(
                    "Market data loaded from %s: %s securities",
                    provider_name,
                    len(quotes),
                )

                return quotes

            except Exception as exc:
                error = f"{provider_name}: {exc}"
                errors.append(error)
                logger.exception("Provider failed: %s", provider_name)

        self.active_provider = None
        self.last_error = " | ".join(errors)

        raise RuntimeError(
            f"All market-data providers failed: {self.last_error}"
        )

    def get_market_status(self) -> Dict[str, Any]:
        for provider in self._providers():
            provider_name = getattr(provider, "name", provider.__class__.__name__)

            try:
                if not provider.health_check():
                    continue

                status = provider.fetch_market_status()

                if isinstance(status, dict) and status:
                    self.active_provider = provider_name
                    return status

            except Exception:
                logger.exception(
                    "Unable to obtain market status from %s",
                    provider_name,
                )

        return {
            "status": "UNKNOWN",
            "provider": None,
            "message": "No market-data provider is currently available.",
        }

    def get_provider_info(self) -> Dict[str, Optional[str]]:
        return {
            "active_provider": self.active_provider,
            "primary_provider": getattr(
                self.primary_provider,
                "name",
                self.primary_provider.__class__.__name__,
            ),
            "last_error": self.last_error,
        }
