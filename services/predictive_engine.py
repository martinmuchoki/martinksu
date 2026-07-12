from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Dict, List

from services.market_data import get_price_history
from services.technical_analysis import safe_float


def _returns(symbol: str) -> List[float]:
    history = get_price_history(symbol, 260)

    closes = [
        safe_float(row.get("close"))
        for row in history
        if safe_float(row.get("close")) > 0
    ]

    return [
        (current / previous) - 1
        for previous, current in zip(closes, closes[1:])
        if previous > 0
    ]


def predict_stock(
    stock: Dict[str, Any],
    technical: Dict[str, Any],
) -> Dict[str, Any]:
    symbol = str(stock.get("symbol") or "").upper()
    price = safe_float(stock.get("price"))
    change_pct = safe_float(stock.get("change_pct"))
    score = safe_float(technical.get("score"), 50)

    returns = _returns(symbol)

    if len(returns) >= 5:
        volatility = pstdev(returns) * math.sqrt(252) * 100
        recent_return = mean(returns[-20:]) * 100
        mode = "HISTORICAL HEURISTIC"
    else:
        volatility = max(abs(change_pct) * 4, 12)
        recent_return = change_pct / 10
        mode = "LIVE SNAPSHOT HEURISTIC"

    expected_return = (
        ((score - 50) / 8)
        + (change_pct * 0.55)
        + (recent_return * 4)
    )

    expected_return = max(-15, min(25, expected_return))

    probability = (
        50
        + ((score - 50) * 0.65)
        + (change_pct * 1.8)
    )

    probability = max(20, min(92, probability))

    if score >= 80:
        holding_days = 20
    elif score >= 65:
        holding_days = 15
    elif score >= 50:
        holding_days = 10
    else:
        holding_days = 5

    expected_drawdown = -max(
        2,
        min(
            20,
            (volatility / math.sqrt(252))
            * math.sqrt(holding_days),
        ),
    )

    target_price = (
        price * (1 + expected_return / 100)
        if price > 0
        else 0
    )

    return {
        "symbol": symbol,
        "name": stock.get("name"),
        "sector": stock.get("sector"),
        "price": round(price, 2),
        "signal": technical.get("signal", "HOLD"),
        "score": int(score),
        "expected_return_pct": round(expected_return, 2),
        "probability_success_pct": round(probability, 2),
        "holding_period_days": holding_days,
        "target_price": round(target_price, 2),
        "maximum_expected_drawdown_pct": round(
            expected_drawdown,
            2,
        ),
        "annualized_volatility_pct": round(volatility, 2),
        "model_mode": mode,
        "disclaimer": (
            "Heuristic estimate — not a guaranteed outcome."
        ),
    }


def build_predictions(
    stocks: List[Dict[str, Any]],
    technicals: List[Dict[str, Any]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    technical_map = {
        item.get("symbol"): item
        for item in technicals
        if isinstance(item, dict) and item.get("symbol")
    }

    predictions = [
        predict_stock(
            stock,
            technical_map.get(stock.get("symbol"), {}),
        )
        for stock in stocks
    ]

    predictions.sort(
        key=lambda item: (
            item["probability_success_pct"],
            item["expected_return_pct"],
            item["score"],
        ),
        reverse=True,
    )

    return predictions[:limit]
