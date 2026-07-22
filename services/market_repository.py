"""
services/market_repository.py

Canonical Market Repository for MIP PRO.

This repository centralizes live NSE quote access through ProviderManager
while preserving the normalized field structure currently consumed by the
application.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any, Dict, Optional

from providers.mystocks_africa_provider import MyStocksAfricaProvider
from providers.provider_manager import ProviderManager
from services.interfaces import IMarketRepository


logger = logging.getLogger(__name__)


class MarketRepository(IMarketRepository):
    """
    Canonical repository for live NSE market data.

    Provider construction remains isolated here so downstream services do not
    depend directly on individual provider implementations.
    """

    def __init__(
        self,
        provider_manager: Optional[ProviderManager] = None,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        if provider_manager is None:
            primary_provider = MyStocksAfricaProvider()

            provider_manager = ProviderManager(
                primary_provider=primary_provider,
            )

        self.provider_manager = provider_manager

        self._quotes: Dict[str, Dict[str, Any]] = {}
        self._market_status: Dict[str, Any] = {}
        self._provider_health: Dict[str, Any] = {}
        self._last_refresh: Optional[str] = None
        self._last_refresh_monotonic: Optional[float] = None

        self.cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self._lock = Lock()

    def _cache_is_fresh(self) -> bool:
        """
        Return True when a populated quote cache is still inside its TTL.
        """
        if not self._quotes:
            return False

        if self._last_refresh_monotonic is None:
            return False

        cache_age = monotonic() - self._last_refresh_monotonic
        return cache_age < self.cache_ttl_seconds

    def refresh(
        self,
        force: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Return normalized live quotes.

        A provider request is made only when the cache has expired, the cache
        is empty, or force=True. If a provider refresh fails, the last valid
        in-memory snapshot remains available.
        """
        if not force and self._cache_is_fresh():
            return dict(self._quotes)

        with self._lock:
            # Another thread may have refreshed while this thread waited.
            if not force and self._cache_is_fresh():
                return dict(self._quotes)

            try:
                raw_quotes = self.provider_manager.get_live_quotes()

                normalized_quotes: Dict[str, Dict[str, Any]] = {}

                for symbol, quote in raw_quotes.items():
                    normalized_quote = self._normalize_quote(
                        symbol=symbol,
                        quote=quote,
                    )

                    if normalized_quote is not None:
                        normalized_quotes[
                            normalized_quote["symbol"]
                        ] = normalized_quote

                if not normalized_quotes:
                    raise RuntimeError(
                        "Provider returned no valid normalized quotes."
                    )

                self._quotes = normalized_quotes
                self._last_refresh = datetime.now(
                    timezone.utc
                ).isoformat()
                self._last_refresh_monotonic = monotonic()

                self._market_status = (
                    self.provider_manager.get_market_status()
                )

                self._provider_health = {
                    **self.provider_manager.get_provider_info(),
                    "healthy": True,
                    "quote_count": len(self._quotes),
                    "last_refresh": self._last_refresh,
                }

                logger.info(
                    "MarketRepository refreshed %d symbols using %s.",
                    len(self._quotes),
                    self._provider_health.get("active_provider"),
                )

            except Exception as exc:
                logger.exception(
                    "MarketRepository refresh failed: %s",
                    exc,
                )

                provider_info = (
                    self.provider_manager.get_provider_info()
                )

                self._provider_health = {
                    **provider_info,
                    "healthy": False,
                    "quote_count": len(self._quotes),
                    "last_refresh": self._last_refresh,
                    "error": str(exc),
                }

                if not self._market_status:
                    self._market_status = {
                        "status": "UNKNOWN",
                        "provider": provider_info.get(
                            "active_provider"
                        ),
                        "message": (
                            "Unable to refresh live market data."
                        ),
                    }

            return dict(self._quotes)

    def get_all_quotes(self) -> Dict[str, Dict[str, Any]]:
        """
        Return a shallow copy of the current quote cache.
        """
        return dict(self._quotes)

    def get_quote(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Return one normalized quote by symbol.
        """
        normalized_symbol = str(symbol).strip().upper()

        quote = self._quotes.get(normalized_symbol)

        return dict(quote) if quote is not None else None

    def get_market_status(self) -> Dict[str, Any]:
        """
        Return the latest market-status payload.
        """
        return dict(self._market_status)

    def get_provider_health(self) -> Dict[str, Any]:
        """
        Return provider and repository health metadata.
        """
        if not self._provider_health:
            provider_info = (
                self.provider_manager.get_provider_info()
            )

            return {
                **provider_info,
                "healthy": False,
                "quote_count": len(self._quotes),
                "last_refresh": self._last_refresh,
            }

        return dict(self._provider_health)

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            if value in (None, ""):
                return default

            return float(value)

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            if value in (None, ""):
                return default

            return int(float(value))

        except (TypeError, ValueError):
            return default

    def _normalize_quote(
        self,
        symbol: str,
        quote: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Convert one provider quote into the canonical application schema.
        """
        if not isinstance(quote, dict):
            return None

        normalized_symbol = str(
            quote.get("symbol") or symbol or ""
        ).strip().upper()

        if not normalized_symbol:
            return None

        price = self._safe_float(
            quote.get("price")
            or quote.get("last_price")
        )

        previous_close = self._safe_float(
            quote.get("previous_close")
            or quote.get("prev_close")
        )

        raw_change = quote.get("change")

        if raw_change in (None, ""):
            change_amount = (
                round(price - previous_close, 4)
                if price > 0 and previous_close > 0
                else 0.0
            )
        else:
            change_amount = self._safe_float(raw_change)

        change_pct = self._safe_float(
            quote.get("change_pct")
            if quote.get("change_pct") not in (None, "")
            else quote.get("change_percent")
        )

        open_price = self._safe_float(
            quote.get("open"),
            default=price,
        )

        if open_price <= 0:
            open_price = price

        raw_high = self._safe_float(quote.get("high"))
        raw_low = self._safe_float(quote.get("low"))

        valid_reference_prices = [
            value
            for value in (
                price,
                previous_close,
                open_price,
            )
            if value > 0
        ]

        if valid_reference_prices:
            high_price = max(
                [raw_high, *valid_reference_prices]
            )

            positive_low_values = [
                value
                for value in (
                    raw_low,
                    *valid_reference_prices,
                )
                if value > 0
            ]

            low_price = (
                min(positive_low_values)
                if positive_low_values
                else 0.0
            )
        else:
            high_price = raw_high
            low_price = raw_low if raw_low > 0 else 0.0

        volume = self._safe_int(quote.get("volume"))

        traded_value = self._safe_float(
            quote.get("value")
            or quote.get("turnover")
        )

        if traded_value <= 0 and price > 0 and volume > 0:
            traded_value = round(price * volume, 2)

        timestamp = (
            quote.get("timestamp")
            or quote.get("last_price_update")
            or quote.get("updated_at")
            or quote.get("checked_at")
            or self._last_refresh
        )

        provider_name = (
            quote.get("provider")
            or quote.get("source")
            or self.provider_manager.active_provider
            or "MyStocks Africa"
        )

        return {
            "symbol": normalized_symbol,
            "name": quote.get("name") or normalized_symbol,
            "price": price,
            "previous_close": previous_close,
            "change": change_amount,
            "change_pct": change_pct,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "volume": volume,
            "value": traded_value,
            "sector": quote.get("sector") or "Unknown",
            "currency": quote.get("currency") or "KES",
            "market_cap": quote.get("market_cap"),
            "pe_ratio": quote.get("pe_ratio"),
            "eps": quote.get("eps"),
            "dividend_yield": quote.get("dividend_yield"),
            "timestamp": timestamp,
            "updated_at": timestamp,
            "provider": provider_name,
            "source": provider_name,
        }
