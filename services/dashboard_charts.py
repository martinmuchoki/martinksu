from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from services.database import get_conn, init_db
from services.institutional_intelligence import build_institutional_profile
from services.screener_engine import run_screener
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


def _get_average_volumes_20d() -> Dict[str, float]:
    """Return each symbol's average volume over its latest 20 sessions."""
    init_db()
    conn = get_conn()

    try:
        rows = conn.execute(
            """
            WITH ranked_volume AS (
                SELECT
                    symbol,
                    volume,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol
                        ORDER BY trade_date DESC
                    ) AS session_rank
                FROM price_history
                WHERE volume IS NOT NULL
                  AND volume > 0
            )
            SELECT
                symbol,
                AVG(volume) AS average_volume_20d
            FROM ranked_volume
            WHERE session_rank <= 20
            GROUP BY symbol
            """
        ).fetchall()

        return {
            str(row["symbol"]): _safe_float(row["average_volume_20d"])
            for row in rows
        }
    finally:
        conn.close()


def _volume_signal(relative_volume: float, change_pct: float) -> str:
    if relative_volume >= 3.0:
        return (
            "INSTITUTIONAL BUYING"
            if change_pct > 0
            else "INSTITUTIONAL DISTRIBUTION"
            if change_pct < 0
            else "INSTITUTIONAL ACTIVITY"
        )

    if relative_volume >= 2.0:
        return (
            "BREAKOUT VOLUME"
            if change_pct > 0
            else "DISTRIBUTION"
            if change_pct < 0
            else "UNUSUAL VOLUME"
        )

    if relative_volume >= 1.5:
        return "ABOVE AVERAGE"

    if relative_volume >= 0.8:
        return "NORMAL"

    return "LOW ACTIVITY"


def _volume_score(relative_volume: float, change_pct: float) -> int:
    rvol_component = min(relative_volume / 3.0, 1.0) * 70
    price_confirmation = min(abs(change_pct) / 5.0, 1.0) * 30

    return max(
        0,
        min(100, round(rvol_component + price_confirmation)),
    )


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

    average_volumes = _get_average_volumes_20d()

    try:
        screener_results = run_screener()
    except Exception as exc:
        print(
            "Institutional score merge skipped:",
            exc,
        )
        screener_results = []

    score_map = {}

    for result in screener_results:
        symbol_key = str(
            result.get("symbol") or ""
        ).upper()

        raw_score = (
            result.get("score")
            if result.get("score") is not None
            else result.get("ai_score")
            if result.get("ai_score") is not None
            else result.get("total_score")
            if result.get("total_score") is not None
            else result.get("confidence")
        )

        try:
            score_map[symbol_key] = round(
                float(raw_score)
            )
        except (TypeError, ValueError):
            continue

    volume_intelligence: List[Dict[str, Any]] = []

    for stock in stocks:
        enriched_stock = dict(stock)
        symbol = str(stock.get("symbol") or "").upper()
        current_volume = _safe_int(stock.get("volume"))
        average_volume = average_volumes.get(symbol, 0.0)
        change_pct = _safe_float(stock.get("change_pct"))

        relative_volume = (
            current_volume / average_volume
            if average_volume > 0
            else 0.0
        )

        enriched_stock.update(
            {
                "volume": current_volume,
                "average_volume_20d": round(average_volume),
                "relative_volume": round(relative_volume, 2),
                "volume_signal": _volume_signal(
                    relative_volume,
                    change_pct,
                ),
                "volume_score": _volume_score(
                    relative_volume,
                    change_pct,
                ),
            }
        )

        ai_score = score_map.get(symbol)

        if ai_score is not None:
            enriched_stock["score"] = ai_score
            enriched_stock["ai_score"] = ai_score

        volume_intelligence.append(enriched_stock)

    active_volume_stocks = [
        item
        for item in volume_intelligence
        if _safe_int(item.get("volume")) > 0
    ]

    # Highest absolute traded volume.
    volume_leaders = sorted(
        active_volume_stocks,
        key=lambda item: _safe_int(
            item.get("volume")
        ),
        reverse=True,
    )[:16]

    stock_total = len(stocks)

    advancing_percentage = (
        len(advancers) / stock_total * 100
        if stock_total
        else 50.0
    )

    volume_leaders = [
        build_institutional_profile(
            item,
            volume_rank=index,
            advancing_percentage=advancing_percentage,
        )
        for index, item in enumerate(
            volume_leaders,
            start=1,
        )
    ]

    # Highest activity relative to the stock's 20-day average.
    unusual_volume = sorted(
        [
            item
            for item in active_volume_stocks
            if _safe_float(
                item.get("relative_volume")
            ) > 0
        ],
        key=lambda item: (
            _safe_float(
                item.get("relative_volume")
            ),
            _safe_int(item.get("volume")),
        ),
        reverse=True,
    )[:16]

    rank_map = {
        item.get("symbol"): index
        for index, item in enumerate(
            volume_leaders,
            start=1,
        )
    }

    unusual_volume = [
        build_institutional_profile(
            item,
            volume_rank=rank_map.get(
                item.get("symbol"),
                99,
            ),
            advancing_percentage=advancing_percentage,
        )
        for item in unusual_volume
    ]

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

    total = len(stocks)

    adv_pct = round(
        len(advancers) / total * 100,
        1,
    ) if total else 0.0

    dec_pct = round(
        len(decliners) / total * 100,
        1,
    ) if total else 0.0

    unc_pct = round(
        len(unchanged) / total * 100,
        1,
    ) if total else 0.0

    ratio = (
        len(advancers) / max(
            len(decliners),
            1,
        )
    )

    if ratio >= 2:
        breadth_signal = "🔥 Strong Bullish"
        breadth_label = "Strong Bullish"
    elif ratio >= 1.3:
        breadth_signal = "🟢 Moderately Bullish"
        breadth_label = "Moderately Bullish"
    elif ratio >= 0.9:
        breadth_signal = "⚪ Neutral"
        breadth_label = "Neutral"
    elif ratio >= 0.6:
        breadth_signal = "🟡 Moderately Bearish"
        breadth_label = "Moderately Bearish"
    else:
        breadth_signal = "🔴 Strong Bearish"
        breadth_label = "Strong Bearish"

    market_pulse = (
        f"{adv_pct}% of NSE stocks advanced today, "
        f"while {dec_pct}% declined and "
        f"{unc_pct}% were unchanged. "
        f"Market breadth is {breadth_label}."
    )

    return {
        "advancers": len(advancers),
        "decliners": len(decliners),
        "unchanged": len(unchanged),
        "total": total,
        "advance_decline_ratio": round(
            len(advancers) / len(decliners),
            2,
        ) if decliners else float(len(advancers)),
        "advancing_percentage": adv_pct,
        "declining_percentage": dec_pct,
        "unchanged_percentage": unc_pct,
        "breadth_signal": breadth_signal,
        "market_pulse": market_pulse,
        "volume_leaders": volume_leaders,
        "unusual_volume": unusual_volume,
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
