from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, List


def detect_market_regime(
    market: Dict[str, Any],
    technicals: List[Dict[str, Any]],
    risk: Dict[str, Any],
) -> Dict[str, Any]:
    valid = [
        item
        for item in technicals
        if isinstance(item, dict) and not item.get("error")
    ]

    bullish = sum(
        1 for item in valid
        if item.get("signal") in {"BUY", "STRONG BUY"}
    )

    bearish = sum(
        1 for item in valid
        if item.get("signal") in {"WATCH", "SELL"}
    )

    breadth = (
        ((bullish - bearish) / len(valid)) * 100
        if valid
        else 0
    )

    average_change = float(
        market.get("average_change") or 0
    )

    score = (
        50
        + average_change * 8
        + breadth * 0.35
    )

    score = max(0, min(100, score))

    if score >= 75:
        regime = "STRONG BULL MARKET"
    elif score >= 60:
        regime = "BULL MARKET"
    elif score >= 40:
        regime = "NEUTRAL / SELECTIVE"
    elif score >= 25:
        regime = "BEAR MARKET"
    else:
        regime = "STRONG BEAR MARKET"

    confidence = min(
        95,
        55 + abs(score - 50),
    )

    return {
        "regime": regime,
        "confidence_pct": round(confidence, 2),
        "regime_score": round(score, 2),
        "breadth_score": round(breadth, 2),
        "bullish_signals": bullish,
        "bearish_signals": bearish,
        "market_risk_level": risk.get(
            "market_risk_level",
            "COLLECTING DATA",
        ),
    }


def analyze_sector_rotation(
    stocks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    grouped = defaultdict(list)

    for stock in stocks:
        sector = stock.get("sector") or "Unknown"
        grouped[sector].append(stock)

    sectors = []

    for sector, items in grouped.items():
        changes = [
            float(item.get("change_pct") or 0)
            for item in items
        ]

        volumes = [
            int(item.get("volume") or 0)
            for item in items
        ]

        average_change = (
            mean(changes)
            if changes
            else 0
        )

        breadth = (
            sum(1 for value in changes if value > 0)
            / len(changes)
            * 100
            if changes
            else 0
        )

        sectors.append({
            "sector": sector,
            "stock_count": len(items),
            "average_change_pct": round(
                average_change,
                2,
            ),
            "positive_breadth_pct": round(
                breadth,
                2,
            ),
            "total_volume": sum(volumes),
            "rotation_score": round(
                average_change * 12
                + breadth * 0.35,
                2,
            ),
        })

    sectors.sort(
        key=lambda item: (
            item["rotation_score"],
            item["total_volume"],
        ),
        reverse=True,
    )

    return {
        "strongest_sector": (
            sectors[0] if sectors else None
        ),
        "weakest_sector": (
            sectors[-1] if sectors else None
        ),
        "sectors": sectors,
    }
