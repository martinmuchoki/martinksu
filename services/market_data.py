from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from services.market_repository import MarketRepository
from services.database import (
    get_conn,
    init_db,
    rows_to_dicts,
    seed_data,
    seed_price_history,
)


_repository = MarketRepository()


def ensure_market_data() -> None:
    """
    Keep the existing database and historical seed data available.
    Live quote snapshots now come from MyStocks Africa.
    """
    init_db()
    seed_data()
    seed_price_history()


def _normalize_live_stock(
    symbol: str,
    quote: Dict[str, Any],
) -> Dict[str, Any]:
    price = float(quote.get("price") or 0)
    previous_close = float(quote.get("previous_close") or 0)

    change_amount = (
        round(price - previous_close, 4)
        if price > 0 and previous_close > 0
        else 0.0
    )

    open_price = float(quote.get("open") or price or 0)
    raw_high = float(quote.get("high") or 0)
    raw_low = float(quote.get("low") or 0)

    valid_prices = [
        value
        for value in (price, previous_close, open_price)
        if value > 0
    ]

    high_price = max(
        [raw_high, *valid_prices]
    ) if valid_prices else raw_high

    positive_lows = [
        value
        for value in (raw_low, *valid_prices)
        if value > 0
    ]

    low_price = min(positive_lows) if positive_lows else 0.0

    return {
        "symbol": symbol,
        "name": quote.get("name") or symbol,
        "price": price,
        "previous_close": previous_close,
        "change": change_amount,
        "change_pct": float(quote.get("change_percent") or 0),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "volume": int(quote.get("volume") or 0),
        "sector": quote.get("sector") or "Unknown",
        "currency": quote.get("currency") or "KES",
        "market_cap": quote.get("market_cap"),
        "pe_ratio": quote.get("pe_ratio"),
        "eps": quote.get("eps"),
        "dividend_yield": quote.get("dividend_yield"),
        "updated_at": (
            quote.get("last_price_update")
            or quote.get("updated_at")
            or quote.get("checked_at")
        ),
        "source": quote.get("source") or "MyStocks Africa",
    }


def get_stocks() -> List[Dict[str, Any]]:
    """
    Return the latest NSE snapshot from MyStocks Africa.

    If the API is temporarily unavailable, fall back to the existing
    local stocks table so the application stays online.
    """
    ensure_market_data()

    try:
        quotes = _repository.refresh()

        if not quotes:
            raise RuntimeError(
                "MarketRepository returned no live quotes."
            )

        stocks = list(quotes.values())

        return sorted(stocks, key=lambda item: item["symbol"])

    except Exception as exc:
        print(f"MyStocks Africa unavailable; using database fallback: {exc}")

        conn = get_conn()

        try:
            rows = conn.execute(
                "SELECT * FROM stocks ORDER BY symbol"
            ).fetchall()
            return rows_to_dicts(rows)

        finally:
            conn.close()


def get_stock(symbol: str) -> Dict[str, Any] | None:
    symbol = symbol.upper().strip()

    for stock in get_stocks():
        if stock.get("symbol") == symbol:
            return stock

    return None


def get_price_history(
    symbol: str,
    limit: int = 260,
) -> List[Dict[str, Any]]:
    """
    Historical OHLCV still comes from the local SQLite price_history table.
    """
    ensure_market_data()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM price_history
            WHERE symbol = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (symbol.upper(), limit),
        ).fetchall()

        return list(reversed(rows_to_dicts(rows)))

    finally:
        conn.close()


def get_market_snapshot() -> Dict[str, Any]:
    stocks = get_stocks()

    valid_stocks = [
        stock
        for stock in stocks
        if isinstance(stock.get("change_pct"), (int, float))
    ]

    gainers = sorted(
        valid_stocks,
        key=lambda item: item.get("change_pct", 0),
        reverse=True,
    )[:5]

    losers = sorted(
        valid_stocks,
        key=lambda item: item.get("change_pct", 0),
    )[:5]

    average_change = (
        round(
            sum(stock.get("change_pct", 0) for stock in valid_stocks)
            / len(valid_stocks),
            2,
        )
        if valid_stocks
        else 0
    )

    if average_change > 1:
        status = "Bullish"
    elif average_change < -1:
        status = "Bearish"
    else:
        status = "Neutral / selective"

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_status": status,
        "average_change": average_change,
        "stocks": stocks,
        "top_gainers": gainers,
        "top_losers": losers,
        "provider": "MyStocks Africa",
        "security_count": len(stocks),
    }
