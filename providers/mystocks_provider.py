from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests


class MyStocksProvider:
    name = "MyStocks"

    BASE_URL = "https://live.mystocks.co.ke"
    CACHE_FILE = Path("data/mystocks_sectors.json")

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 NSE-Signal-Bot/10.4",
                "Accept": "application/json",
                "Referer": "https://tickers.mystocks.co.ke/",
            }
        )

    @staticmethod
    def _sector_key() -> str:
        now = datetime.now()

        # Matches the JavaScript format:
        # year + zero-based month + browser weekday + hour
        return (
            f"{now.year}"
            f"{now.month - 1:02d}"
            f"{(now.weekday() + 1) % 7:02d}"
            f"{now.hour:02d}"
        )

    def _sector_url(self) -> str:
        return f"{self.BASE_URL}/ajax/stocksectors/{self._sector_key()}"

    def health_check(self) -> bool:
        try:
            response = self.session.get(
                self._sector_url(),
                timeout=self.timeout,
            )
            return (
                response.status_code == 200
                and "application/json"
                in response.headers.get("content-type", "")
            )
        except requests.RequestException:
            return False

    def fetch_sectors(self) -> Dict[str, Dict[str, str]]:
        response = self.session.get(
            self._sector_url(),
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict) or not data:
            raise ValueError("MyStocks returned invalid sector data.")

        normalized: Dict[str, Dict[str, str]] = {}

        for sector, securities in data.items():
            if not isinstance(securities, dict):
                continue

            normalized[str(sector)] = {
                str(symbol).strip(): str(company).strip()
                for symbol, company in securities.items()
                if symbol and company
            }

        if not normalized:
            raise ValueError("No valid MyStocks sectors were found.")

        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        with self.CACHE_FILE.open("w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=2, ensure_ascii=False)

        return normalized

    def fetch_security_master(self) -> Dict[str, Dict[str, Any]]:
        sectors = self.fetch_sectors()
        master: Dict[str, Dict[str, Any]] = {}

        for sector, securities in sectors.items():
            for symbol, company in securities.items():
                master[symbol] = {
                    "symbol": symbol,
                    "name": company,
                    "sector": sector,
                    "market": "NSE",
                    "currency": "KES",
                    "asset_type": self._asset_type(symbol, sector),
                    "active": True,
                    "source": self.name,
                }

        return master

    @staticmethod
    def _asset_type(symbol: str, sector: str) -> str:
        if sector == "Exchange Traded Funds":
            return "ETF"

        if sector == "Real Estate Investment Trusts":
            return "REIT"

        if symbol.endswith("-R"):
            return "RIGHTS"

        if symbol.startswith("KPLC-P"):
            return "PREFERENCE_SHARE"

        return "EQUITY"

    def fetch_quotes(self) -> Dict[str, Dict[str, Any]]:
        # Live quote parser will be implemented next.
        return {}

    def fetch_market_status(self) -> Dict[str, Any]:
        return {
            "status": "CONNECTED" if self.health_check() else "UNAVAILABLE",
            "provider": self.name,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
