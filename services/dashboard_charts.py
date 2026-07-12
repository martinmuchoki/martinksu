from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from services.database import get_conn, init_db
from services.market_data import get_market_snapshot
from services.performance_engine import get_performance_summary


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def get_market_breadth() -> Dict[str, Any]:
    market = get_market_snapshot()
    stocks = market.get("stocks", [])

    advancers = [
        stock
        for stock in stocks
        if _safe_float(stock.get("change_pct")) > 0
    ]

    decliners = [
        stock
        for stock in stocks
        if _safe_float(stock.get("change_pct")) < 0
    ]

    unchanged = [
        stock
        for stock in stocks
        if _safe_float(stock.get("change_pct")) == 0
    ]

    volume_leaders = sorted(
        stocks,
        key=lambda item: _safe_int(item.get("volume")),
        reverse=True,
    )[:16]

    gainers = sorted(
        stocks,
        key=lambda item: _safe_float(item.get("change_pct")),
        reverse=True,
    )[:10]

    losers = sorted(
        stocks,
        key=lambda item: _safe_float(item.get("change_pct")),
    )[:10]

    total = len(stocks)

    return {
        "advancers": len(advancers),
        "decliners": len(decliners),
        "unchanged": len(unchanged),
        "total": total,
        "advance_decline_ratio": round(
            len(advancers) / len(decliners),
            2,
        ) if decliners else float(len(advancers)),
        "advancing_percentage": round(
            len(advancers) / total * 100,
            2,
        ) if total else 0,
        "declining_percentage": round(
            len(decliners) / total * 100,
            2,
        ) if total else 0,
        "volume_leaders": volume_leaders,
        "top_gainers": gainers,
        "top_losers": losers,
        "generated_at": datetime.now().isoformat(),
    }


def get_market_history_chart(
    symbol: str = "SCOM",
    limit: int = 60,
) -> Dict[str, Any]:
    init_db()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT trade_date, close, volume
            FROM price_history
            WHERE symbol = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (symbol.upper(), limit),
        ).fetchall()

    finally:
        conn.close()

    rows = list(reversed(rows))

    return {
        "symbol": symbol.upper(),
        "labels": [
            row["trade_date"]
            for row in rows
        ],
        "prices": [
            round(_safe_float(row["close"]), 2)
            for row in rows
        ],
        "volumes": [
            _safe_int(row["volume"])
            for row in rows
        ],
    }


def get_portfolio_history_chart(
    limit: int = 60,
) -> Dict[str, Any]:
    init_db()
    conn = get_conn()

    try:
        holdings = conn.execute(
            """
            SELECT symbol, shares
            FROM portfolio
            WHERE shares > 0
            """
        ).fetchall()

        values_by_date: Dict[str, float] = defaultdict(float)

        for holding in holdings:
            rows = conn.execute(
                """
                SELECT trade_date, close
                FROM price_history
                WHERE symbol = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (holding["symbol"], limit),
            ).fetchall()

            for row in rows:
                values_by_date[row["trade_date"]] += (
                    _safe_float(row["close"])
                    * _safe_float(holding["shares"])
                )

    finally:
        conn.close()

    labels = sorted(values_by_date.keys())[-limit:]

    return {
        "labels": labels,
        "values": [
            round(values_by_date[label], 2)
            for label in labels
        ],
    }


def get_ai_confidence_history(
    limit: int = 60,
) -> Dict[str, Any]:
    init_db()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT
                recommendation_date,
                AVG(confidence) AS average_confidence,
                COUNT(*) AS recommendation_count
            FROM ai_recommendations
            GROUP BY recommendation_date
            ORDER BY recommendation_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    except Exception:
        rows = []

    finally:
        conn.close()

    rows = list(reversed(rows))

    return {
        "labels": [
            row["recommendation_date"]
            for row in rows
        ],
        "confidence": [
            round(
                _safe_float(row["average_confidence"]),
                2,
            )
            for row in rows
        ],
        "recommendations": [
            _safe_int(row["recommendation_count"])
            for row in rows
        ],
    }


def get_sector_chart() -> Dict[str, Any]:
    market = get_market_snapshot()
    grouped: Dict[str, List[float]] = defaultdict(list)

    for stock in market.get("stocks", []):
        sector = stock.get("sector") or "Unknown"

        grouped[sector].append(
            _safe_float(stock.get("change_pct"))
        )

    rows = []

    for sector, changes in grouped.items():
        average_change = (
            sum(changes) / len(changes)
            if changes
            else 0
        )

        rows.append({
            "sector": sector,
            "average_change": round(
                average_change,
                2,
            ),
        })

    rows.sort(
        key=lambda item: item["average_change"],
        reverse=True,
    )

    rows = rows[:12]

    return {
        "labels": [
            item["sector"]
            for item in rows
        ],
        "values": [
            item["average_change"]
            for item in rows
        ],
    }


def get_dashboard_chart_data(
    symbol: str = "SCOM",
) -> Dict[str, Any]:
    return {
        "market_history": get_market_history_chart(symbol),
        "portfolio_history": get_portfolio_history_chart(),
        "ai_confidence": get_ai_confidence_history(),
        "sector_rotation": get_sector_chart(),
        "breadth": get_market_breadth(),
        "performance": get_performance_summary(),
        "generated_at": datetime.now().isoformat(),
    }
