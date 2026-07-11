from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup


class MyStocksSnapshot:
    name = "MyStocks Snapshot"

    SNAPSHOT_URL = (
        "https://tickers.mystocks.co.ke/"
        "ticker/RMWX$?app=FIB;f=mslFrame0;d=fib.co.ke"
    )

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/150 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Referer": "https://fib.co.ke/live-markets/",
            }
        )

    @staticmethod
    def _number(value: str) -> float:
        cleaned = (
            value.replace(",", "")
            .replace("%", "")
            .replace("▲", "")
            .replace("▼", "")
            .strip()
        )

        if cleaned in {"", "-", "--", "N/A"}:
            return 0.0

        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    @staticmethod
    def _integer(value: str) -> int:
        try:
            return int(MyStocksSnapshot._number(value))
        except (TypeError, ValueError):
            return 0

    def fetch_html(self) -> str:
        response = self.session.get(
            self.SNAPSHOT_URL,
            timeout=self.timeout,
        )
        response.raise_for_status()

        body = response.text
        content_type = response.headers.get("content-type", "")

        print("Snapshot HTTP Status:", response.status_code)
        print("Snapshot Content-Type:", content_type)
        print("Snapshot Length:", len(body))
        print("Snapshot Preview:", repr(body[:150]))

        if not body.strip():
            raise ValueError("Snapshot endpoint returned an empty response.")

        html_markers = (
            "<html",
            "<!doctype",
            "<table",
            "board_table",
            "myStocks",
        )

        if not any(marker.lower() in body.lower() for marker in html_markers):
            raise ValueError(
                "Snapshot response does not appear to contain the market HTML."
            )

        return body

    def fetch_quotes(self) -> Dict[str, Dict[str, Any]]:
        html = self.fetch_html()
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table", id="board_table")

        if table is None:
            raise ValueError("Could not find the myStocks market table.")

        quotes: Dict[str, Dict[str, Any]] = {}

        for row in table.find_all("tr"):
            cells = row.find_all("td")

            if len(cells) < 10:
                continue

            symbol = row.get("id", "").strip()

            if not symbol:
                symbol = cells[0].get_text(" ", strip=True).split()[0]

            if not symbol:
                continue

            previous_close = self._number(cells[1].get_text(" ", strip=True))
            latest_price = self._number(cells[2].get_text(" ", strip=True))
            price_change = self._number(cells[3].get_text(" ", strip=True))
            percent_text = cells[4].get_text(" ", strip=True)
            change_percent = self._number(percent_text)
            high = self._number(cells[5].get_text(" ", strip=True))
            low = self._number(cells[6].get_text(" ", strip=True))
            average_price = self._number(cells[7].get_text(" ", strip=True))
            volume = self._integer(cells[8].get_text(" ", strip=True))
            last_trade_time = cells[9].get_text(" ", strip=True) or None

            if "▼" in percent_text and change_percent > 0:
                change_percent = -change_percent

            quotes[symbol] = {
                "symbol": symbol,
                "previous_close": previous_close,
                "price": latest_price,
                "change": price_change,
                "change_percent": change_percent,
                "high": high,
                "low": low,
                "average_price": average_price,
                "volume": volume,
                "last_trade_time": last_trade_time,
                "source": self.name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        if not quotes:
            raise ValueError("No quotes were parsed from the market table.")

        return quotes
