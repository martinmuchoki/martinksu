from __future__ import annotations

from typing import Any, Dict, List

from services.market_data import get_market_snapshot
from services.technical_analysis import technical_score


def _risk_level(stock: Dict[str, Any]) -> str:
    change_pct = abs(float(stock.get("change_pct") or 0))
    volume = int(stock.get("volume") or 0)

    if change_pct >= 6 or volume < 500:
        return "HIGH RISK"

    if change_pct >= 3 or volume < 5_000:
        return "MODERATE RISK"

    return "LOW RISK"


def _position_size(confidence: int, risk: str) -> int:
    if risk == "HIGH RISK":
        return 0

    if confidence >= 75 and risk == "LOW RISK":
        return 10

    if confidence >= 60:
        return 5

    return 0


def run_screener() -> List[Dict[str, Any]]:
    market = get_market_snapshot()
    results: List[Dict[str, Any]] = []

    for stock in market.get("stocks", []):
        try:
            analysis = technical_score(stock)

            confidence = int(analysis.get("score") or 0)
            risk = _risk_level(stock)

            results.append(
                {
                    "symbol": stock["symbol"],
                    "name": stock.get("name") or stock["symbol"],

                    # Always use the latest MyStocks Africa price.
                    "price": float(stock.get("price") or 0),

                    "decision": analysis.get("signal", "HOLD"),
                    "confidence": confidence,
                    "risk": risk,
                    "position": _position_size(confidence, risk),

                    "change_pct": float(stock.get("change_pct") or 0),
                    "volume": int(stock.get("volume") or 0),
                    "sector": stock.get("sector") or "Unknown",
                    "source": stock.get("source") or "MyStocks Africa",

                    "rsi": analysis.get("rsi"),
                    "macd": analysis.get("macd"),
                    "trend": analysis.get("trend"),
                    "reasons": analysis.get("reasons", []),
                }
            )

        except Exception as exc:
            print(f"Skipping {stock.get('symbol', 'UNKNOWN')}: {exc}")

    results.sort(
        key=lambda item: (
            item["confidence"],
            item["change_pct"],
            item["volume"],
        ),
        reverse=True,
    )

    return results
