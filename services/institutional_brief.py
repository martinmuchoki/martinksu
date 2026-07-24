from __future__ import annotations

from typing import Any, Dict, List

from services.signal_presenter import get_signal_presenter
from services.telegram_bot import send_telegram_alert


def send_institutional_brief(
    market: Dict[str, Any],
    screener: List[Dict[str, Any]],
    performance: Dict[str, Any],
    optimizer: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Present and send the institutional brief.

    Formatting belongs to SignalPresenter. This module remains the
    Telegram delivery orchestration boundary.
    """
    message = (
        get_signal_presenter()
        .build_institutional_brief(
            market=market,
            screener=screener,
            performance=performance,
            optimizer=optimizer,
        )
    )

    result = send_telegram_alert(message)

    return {
        **result,
        "message_preview": message[:500],
    }
