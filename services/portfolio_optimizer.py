from __future__ import annotations

from typing import Any, Dict, List


RISK_MULTIPLIERS = {
    "LOW RISK": 1.0,
    "MODERATE RISK": 0.7,
    "HIGH RISK": 0.3,
}


def build_optimized_portfolio(
    screener_results: List[Dict[str, Any]],
    capital: float = 100_000,
    invested_percentage: float = 75,
    maximum_positions: int = 7,
) -> Dict[str, Any]:
    capital = max(0.0, float(capital or 0))
    investable_amount = capital * (invested_percentage / 100)
    cash_reserve = capital - investable_amount

    eligible = []

    for item in screener_results:
        confidence = int(item.get("confidence") or 0)
        price = float(item.get("price") or 0)
        decision = str(item.get("decision") or "").upper()
        risk = str(item.get("risk") or "MODERATE RISK")

        if price <= 0:
            continue

        if confidence < 60:
            continue

        if decision not in {"BUY", "STRONG BUY"}:
            continue

        multiplier = RISK_MULTIPLIERS.get(risk, 0.6)
        score = confidence * multiplier

        eligible.append(
            {
                **item,
                "optimizer_score": score,
            }
        )

    eligible.sort(
        key=lambda item: (
            item["optimizer_score"],
            item.get("volume", 0),
        ),
        reverse=True,
    )

    selected = eligible[:maximum_positions]

    if not selected:
        return {
            "capital": round(capital, 2),
            "investable_amount": 0.0,
            "cash_reserve": round(capital, 2),
            "invested_percentage": 0.0,
            "cash_percentage": 100.0,
            "positions": [],
            "position_count": 0,
            "risk_level": "CAPITAL PRESERVATION",
            "message": "No qualifying BUY opportunities are currently available.",
        }

    sector_usage: Dict[str, float] = {}
    raw_total = sum(
        item["optimizer_score"]
        for item in selected
    )

    positions = []

    for item in selected:
        raw_weight = (
            item["optimizer_score"] / raw_total
            if raw_total
            else 0
        )

        weight_pct = raw_weight * invested_percentage
        weight_pct = min(weight_pct, 20.0)

        sector = item.get("sector") or "Unknown"
        current_sector_weight = sector_usage.get(sector, 0.0)

        if current_sector_weight + weight_pct > 35:
            weight_pct = max(
                0,
                35 - current_sector_weight,
            )

        if weight_pct <= 0:
            continue

        sector_usage[sector] = (
            current_sector_weight + weight_pct
        )

        allocation_amount = capital * (weight_pct / 100)
        price = float(item["price"])
        estimated_shares = int(allocation_amount // price)

        positions.append(
            {
                "symbol": item["symbol"],
                "name": item.get("name"),
                "sector": sector,
                "decision": item.get("decision"),
                "confidence": item.get("confidence"),
                "risk": item.get("risk"),
                "price": round(price, 2),
                "weight_pct": round(weight_pct, 2),
                "allocation_amount": round(
                    allocation_amount,
                    2,
                ),
                "estimated_shares": estimated_shares,
            }
        )

    actual_invested_pct = round(
        sum(position["weight_pct"] for position in positions),
        2,
    )

    actual_invested_amount = round(
        capital * actual_invested_pct / 100,
        2,
    )

    actual_cash = round(
        capital - actual_invested_amount,
        2,
    )

    average_confidence = (
        round(
            sum(
                float(position["confidence"] or 0)
                for position in positions
            )
            / len(positions),
            2,
        )
        if positions
        else 0
    )

    high_risk_count = sum(
        1
        for position in positions
        if position["risk"] == "HIGH RISK"
    )

    if high_risk_count:
        risk_level = "HIGH"
    elif any(
        position["risk"] == "MODERATE RISK"
        for position in positions
    ):
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "capital": round(capital, 2),
        "investable_amount": actual_invested_amount,
        "cash_reserve": actual_cash,
        "invested_percentage": actual_invested_pct,
        "cash_percentage": round(
            100 - actual_invested_pct,
            2,
        ),
        "positions": positions,
        "position_count": len(positions),
        "average_confidence": average_confidence,
        "risk_level": risk_level,
        "sector_exposure": sector_usage,
        "message": (
            "Allocation prioritizes high-confidence BUY signals, "
            "liquidity, risk control and sector diversification."
        ),
    }
