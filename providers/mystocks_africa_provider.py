from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests


class MyStocksAfricaProvider:
    name = "MyStocks Africa"

    BASE_URL = "https://mystocks.africa/api/v1"
    NSE_ENDPOINT = "/stocks?exchange=NSE"

    CACHE_FILE = Path("data/mystocks_africa_nse.json")
    QUOTES_FILE = Path("data/live_quotes.json")

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "NSE-Signal-Bot/11.2",
            }
        )

    def _get_nse_stocks(self) -> List[Dict[str, Any]]:
        response = self.session.get(
            f"{self.BASE_URL}{self.NSE_ENDPOINT}",
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("MyStocks Africa returned an invalid stock list.")

        stocks = [
            item
            for item in payload
            if isinstance(item, dict)
            and item.get("exchange") == "NSE"
            and item.get("listingStatus") == "ACTIVE"
        ]

        if not stocks:
            raise ValueError("No active NSE stocks were returned.")

        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.CACHE_FILE.write_text(
            json.dumps(stocks, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return stocks

    @staticmethod
    def _symbol(item: Dict[str, Any]) -> str:
        symbol = str(item.get("symbol") or "").strip().upper()

        if symbol.endswith(".KE"):
            symbol = symbol[:-3]

        return symbol

    @staticmethod
    def _number(value: Any) -> float:
        if value is None or value == "":
            return 0.0

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return 0

    def health_check(self) -> bool:
        try:
            stocks = self._get_nse_stocks()
            return len(stocks) > 0
        except Exception:
            return False

    def fetch_security_master(self) -> Dict[str, Dict[str, Any]]:
        stocks = self._get_nse_stocks()
        master: Dict[str, Dict[str, Any]] = {}

        for item in stocks:
            symbol = self._symbol(item)

            if not symbol:
                continue

            master[symbol] = {
                "symbol": symbol,
                "provider_symbol": item.get("symbol"),
                "name": item.get("name"),
                "exchange": item.get("exchange"),
                "exchange_mic": item.get("exchangeMic"),
                "currency": item.get("currency", "KES"),
                "sector": item.get("sector"),
                "industry": item.get("industry"),
                "asset_type": item.get("assetType", "STOCK"),
                "listing_status": item.get("listingStatus"),
                "isin": item.get("isin"),
                "market_cap": item.get("marketCap"),
                "pe_ratio": item.get("peRatio"),
                "eps": item.get("eps"),
                "dividend_per_share": item.get("dividendPerShare"),
                "dividend_yield": item.get("dividendYield"),
                "shares_outstanding": item.get("sharesOutstanding"),
                "description": item.get("description"),
                "logo_url": item.get("logoUrl")
                or (item.get("logo") or {}).get("imageUrl"),
                "source": self.name,
                "provider_id": item.get("id"),
                "ticker_id": item.get("tickerId"),
            }

        return master

    def fetch_quotes(self) -> Dict[str, Dict[str, Any]]:
        stocks = self._get_nse_stocks()
        quotes: Dict[str, Dict[str, Any]] = {}
        checked_at = datetime.now(timezone.utc).isoformat()

        for item in stocks:
            symbol = self._symbol(item)

            if not symbol:
                continue

            quotes[symbol] = {
                "symbol": symbol,
                "provider_symbol": item.get("symbol"),
                "name": item.get("name"),
                "price": self._number(item.get("price")),
                "previous_close": self._number(item.get("previousClose")),
                "change_percent": self._number(item.get("change")),
                "open": self._number(item.get("openPrice")),
                "high": self._number(item.get("dayHigh")),
                "low": self._number(item.get("dayLow")),
                "volume": self._integer(item.get("volume")),
                "market_cap": item.get("marketCap"),
                "pe_ratio": item.get("peRatio"),
                "eps": item.get("eps"),
                "dividend_yield": item.get("dividendYield"),
                "sector": item.get("sector"),
                "currency": item.get("currency", "KES"),
                "last_price_update": item.get("lastPriceUpdate"),
                "updated_at": item.get("updatedAt"),
                "source": self.name,
                "checked_at": checked_at,
            }

        if not quotes:
            raise ValueError("No NSE quotes were normalized.")

        self.QUOTES_FILE.write_text(
            json.dumps(quotes, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return quotes

    def fetch_market_status(self) -> Dict[str, Any]:
        stocks = self._get_nse_stocks()

        timestamps = [
            item.get("lastPriceUpdate")
            for item in stocks
            if item.get("lastPriceUpdate")
        ]

        latest_timestamp = max(timestamps) if timestamps else None

        return {
            "status": "AVAILABLE",
            "exchange": "Nairobi Securities Exchange",
            "exchange_code": "NSE",
            "currency": "KES",
            "security_count": len(stocks),
            "latest_price_update": latest_timestamp,
            "provider": self.name,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
