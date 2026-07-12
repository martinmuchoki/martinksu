from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from services.telegram_bot import send_telegram_alert


NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def build_institutional_brief(
    market: Dict[str, Any],
    screener: List[Dict[str, Any]],
    performance: Dict[str, Any],
    optimizer: Dict[str, Any],
) -> str:
    now = datetime.now(NAIROBI_TZ)

    lines = [
        "MIP PRO",
        "",
        f"Market: {market.get('market_status', 'Unknown')}",
        f"Average change: {market.get('average_change', 0)}%",
        f"Securities: {len(market.get('stocks', []))}",
        "",
        "Top Opportunities",
    ]

    for index, item in enumerate(screener[:5], start=1):
        lines.append(
            f"{index}. {item.get('symbol')} "
            f"{item.get('decision')} "
            f"{item.get('confidence')}% "
            f"@ KSh {item.get('price')}"
        )

    lines.extend(
        [
            "",
            "AI Performance",
            f"Recommendations: {performance.get('recommendations', 0)}",
            f"Accuracy: {performance.get('accuracy', 0)}%",
            f"Average return: {performance.get('average_return', 0)}%",
            "",
            "Portfolio Optimizer",
            f"Positions: {optimizer.get('position_count', 0)}",
            f"Invested: {optimizer.get('invested_percentage', 0)}%",
            f"Cash: {optimizer.get('cash_percentage', 100)}%",
            f"Risk: {optimizer.get('risk_level', 'Unknown')}",
            "",
            f"Generated: {now.strftime('%Y-%m-%d %H:%M EAT')}",
        ]
    )

    return "\n".join(lines)


def send_institutional_brief(
    market: Dict[str, Any],
    screener: List[Dict[str, Any]],
    performance: Dict[str, Any],
    optimizer: Dict[str, Any],
) -> Dict[str, Any]:
    message = build_institutional_brief(
        market,
        screener,
        performance,
        optimizer,
    )

    result = send_telegram_alert(message)

    return {
        **result,
        "message_preview": message[:500],
    }
