from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv


load_dotenv()


class MansaProvider:
    name = "Mansa API"

    def __init__(self, timeout: int = 20) -> None:
        self.base_url = os.getenv(
            "MANSA_BASE_URL",
            "https://mansaapi.com",
        ).rstrip("/")

        self.api_key = os.getenv("MANSA_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise RuntimeError("MANSA_API_KEY is missing from .env")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "NSE-Signal-Bot/11.2",
            }
        )

    def _get(self, path: str) -> Dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}{path}",
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("Mansa returned an invalid response.")

        if payload.get("success") is False:
            error = payload.get("error", {})
            raise RuntimeError(
                error.get("message", "Mansa API request failed.")
            )

        return payload

    def health_check(self) -> bool:
        try:
            kenya = self.fetch_kenya_exchange()
            return kenya.get("status") == "live"
        except Exception:
            return False

    def fetch_exchanges(self) -> List[Dict[str, Any]]:
        payload = self._get("/api/v1/markets/exchanges")
        data = payload.get("data", [])

        if not isinstance(data, list):
            raise ValueError("Invalid exchanges response.")

        return data

    def fetch_kenya_exchange(self) -> Dict[str, Any]:
        for exchange in self.fetch_exchanges():
            if exchange.get("id") == "kenya":
                return exchange

        raise LookupError("Kenya exchange was not found.")

    def fetch_market_status(self) -> Dict[str, Any]:
        kenya = self.fetch_kenya_exchange()

        return {
            "status": str(kenya.get("status", "unknown")).upper(),
            "exchange": kenya.get("name"),
            "currency": kenya.get("currency"),
            "timezone": kenya.get("timezone"),
            "trading_hours": kenya.get("trading_hours"),
            "index_value": kenya.get("index_value"),
            "index_change_percent": kenya.get("index_change_pct"),
            "stocks_count": kenya.get("stocks_count"),
            "source_updated_at": kenya.get("last_updated"),
            "provider": self.name,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def fetch_quotes(self) -> Dict[str, Dict[str, Any]]:
        # Add after confirming the documented NSE stocks endpoint.
        return {}
