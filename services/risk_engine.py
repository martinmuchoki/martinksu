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


def _maximum_drawdown(returns: List[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0

    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)

        if peak:
            worst = min(worst, (equity / peak) - 1)

    return worst * 100


def stock_risk_metrics(symbol: str) -> Dict[str, Any]:
    symbol = symbol.upper()
    returns = _returns(symbol)

    if len(returns) < 5:
        return {
            "symbol": symbol,
            "history_rows": len(returns) + 1,
            "volatility_pct": 0,
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "maximum_drawdown_pct": 0,
            "var_95_pct": 0,
            "cvar_95_pct": 0,
            "risk_level": "INSUFFICIENT HISTORY",
        }

    average = mean(returns)
    deviation = pstdev(returns)

    downside = [
        value
        for value in returns
        if value < 0
    ]

    downside_deviation = (
        pstdev(downside)
        if len(downside) >= 2
        else deviation
    )

    sharpe = (
        average / deviation * math.sqrt(252)
        if deviation > 0
        else 0
    )

    sortino = (
        average / downside_deviation * math.sqrt(252)
        if downside_deviation > 0
        else 0
    )

    annualized_volatility = deviation * math.sqrt(252) * 100

    ordered = sorted(returns)
    var_index = max(
        0,
        int(len(ordered) * 0.05) - 1,
    )

    var_95 = ordered[var_index] * 100

    tail = [
        value * 100
        for value in returns
        if value * 100 <= var_95
    ]

    cvar_95 = mean(tail) if tail else var_95
    drawdown = _maximum_drawdown(returns)

    if annualized_volatility >= 45 or drawdown <= -30:
        risk_level = "HIGH"
    elif annualized_volatility >= 25 or drawdown <= -15:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "symbol": symbol,
        "history_rows": len(returns) + 1,
        "volatility_pct": round(annualized_volatility, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "maximum_drawdown_pct": round(drawdown, 2),
        "var_95_pct": round(var_95, 2),
        "cvar_95_pct": round(cvar_95, 2),
        "risk_level": risk_level,
    }


def build_market_risk(
    stocks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    selected = sorted(
        stocks,
        key=lambda item: int(item.get("volume") or 0),
        reverse=True,
    )[:20]

    metrics = [
        stock_risk_metrics(stock["symbol"])
        for stock in selected
        if stock.get("symbol")
    ]

    valid = [
        item
        for item in metrics
        if item["risk_level"] != "INSUFFICIENT HISTORY"
    ]

    if not valid:
        return {
            "market_risk_level": "COLLECTING DATA",
            "average_volatility_pct": 0,
            "average_sharpe_ratio": 0,
            "average_sortino_ratio": 0,
            "worst_drawdown_pct": 0,
            "average_var_95_pct": 0,
            "symbols_analyzed": 0,
            "stocks": metrics,
        }

    volatility = mean(
        item["volatility_pct"]
        for item in valid
    )

    drawdown = min(
        item["maximum_drawdown_pct"]
        for item in valid
    )

    if volatility >= 40 or drawdown <= -30:
        risk_level = "HIGH"
    elif volatility >= 25 or drawdown <= -15:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "market_risk_level": risk_level,
        "average_volatility_pct": round(volatility, 2),
        "average_sharpe_ratio": round(
            mean(item["sharpe_ratio"] for item in valid),
            2,
        ),
        "average_sortino_ratio": round(
            mean(item["sortino_ratio"] for item in valid),
            2,
        ),
        "worst_drawdown_pct": round(drawdown, 2),
        "average_var_95_pct": round(
            mean(item["var_95_pct"] for item in valid),
            2,
        ),
        "symbols_analyzed": len(valid),
        "stocks": metrics,
    }
