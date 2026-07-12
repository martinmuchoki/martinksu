from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

from services.database import get_conn, init_db
from services.market_data import get_market_snapshot


NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def sanitize_ohlcv(stock: Dict[str, Any]) -> Dict[str, Any] | None:
    symbol = str(stock.get("symbol") or "").strip().upper()
    close_price = safe_float(stock.get("price"))

    if not symbol or close_price <= 0:
        return None

    previous_close = safe_float(
        stock.get("previous_close"),
        close_price,
    )

    open_price = safe_float(
        stock.get("open"),
        previous_close or close_price,
    )

    if open_price <= 0:
        open_price = previous_close or close_price

    raw_high = safe_float(stock.get("high"))
    raw_low = safe_float(stock.get("low"))

    valid_prices = [
        price
        for price in (
            open_price,
            close_price,
            previous_close,
            raw_high,
            raw_low,
        )
        if price > 0
    ]

    # The source high/low fields may belong to an older snapshot.
    # Until validated, store a safe OHLC bar using open and close only.
    high_price = max(open_price, close_price)
    low_price = min(open_price, close_price)
    volume = max(0, safe_int(stock.get("volume")))

    return {
        "symbol": symbol,
        "open": round(open_price, 4),
        "high": round(high_price, 4),
        "low": round(low_price, 4),
        "close": round(close_price, 4),
        "volume": volume,
    }


def collect_daily_history() -> Dict[str, Any]:
    init_db()

    snapshot = get_market_snapshot()
    stocks = snapshot.get("stocks", [])

    now = datetime.now(NAIROBI_TZ)
    trade_date = now.date().isoformat()
    collected_at = now.isoformat()

    if now.weekday() >= 5:
        return {
            "success": False,
            "reason": "NSE is closed on weekends",
            "trade_date": trade_date,
            "saved": 0,
            "collected_at": collected_at,
        }

    inserted = 0
    skipped = []
    records = []

    for stock in stocks:
        record = sanitize_ohlcv(stock)

        if record is None:
            skipped.append(
                {
                    "symbol": stock.get("symbol", "UNKNOWN"),
                    "reason": "Missing symbol or valid price",
                }
            )
            continue

        records.append(record)

    conn = get_conn()

    try:
        for record in records:
            conn.execute(
                """
                INSERT OR REPLACE INTO price_history(
                    symbol,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    volume
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["symbol"],
                    trade_date,
                    record["open"],
                    record["high"],
                    record["low"],
                    record["close"],
                    record["volume"],
                ),
            )

            conn.execute(
                """
                UPDATE stocks
                SET price = ?,
                    volume = ?,
                    updated_at = ?
                WHERE symbol = ?
                """,
                (
                    record["close"],
                    record["volume"],
                    collected_at,
                    record["symbol"],
                ),
            )

            inserted += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "success": True,
        "trade_date": trade_date,
        "provider": snapshot.get("provider", "MyStocks Africa"),
        "received": len(stocks),
        "saved": inserted,
        "skipped_count": len(skipped),
        "skipped": skipped[:20],
        "collected_at": collected_at,
    }
