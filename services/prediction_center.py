from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from services.ai_conviction_engine import (
    build_conviction_profiles,
)
from services.dashboard_charts import get_market_breadth
from services.learning_engine import get_learning_summary
from services.market_data import get_market_snapshot
from services.market_regime_engine import (
    build_market_regime,
)
from services.predictive_engine import build_predictions
from services.risk_engine import build_market_risk
from services.screener_engine import run_screener
from services.technical_analysis import analyze_market


KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _normalise_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _build_summary(
    profiles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total = len(profiles)

    strong_buy_count = sum(
        1
        for item in profiles
        if item.get("signal") == "STRONG BUY"
    )

    buy_count = sum(
        1
        for item in profiles
        if item.get("signal") == "BUY"
    )

    hold_count = sum(
        1
        for item in profiles
        if item.get("signal") == "HOLD"
    )

    watch_count = sum(
        1
        for item in profiles
        if item.get("signal") == "WATCH"
    )

    avoid_count = sum(
        1
        for item in profiles
        if item.get("signal") == "AVOID"
    )

    prediction_profiles = [
        item
        for item in profiles
        if item.get("has_prediction", False)
    ]

    average_confidence = (
        round(
            sum(
                _safe_float(item.get("confidence"))
                for item in profiles
            ) / total,
            2,
        )
        if total
        else 0.0
    )

    average_conviction = (
        round(
            sum(
                _safe_float(
                    item.get("conviction_score")
                )
                for item in profiles
            ) / total,
            2,
        )
        if total
        else 0.0
    )

    average_expected_return = (
        round(
            sum(
                _safe_float(
                    item.get("expected_return")
                )
                for item in prediction_profiles
            ) / len(prediction_profiles),
            2,
        )
        if prediction_profiles
        else 0.0
    )

    highest_conviction = (
        profiles[0]
        if profiles
        else {}
    )

    best_expected_return = max(
        prediction_profiles,
        key=lambda item: _safe_float(
            item.get("expected_return")
        ),
        default={},
    )

    institutional_buying_count = sum(
        1
        for item in profiles
        if any(
            label in str(
                item.get("institutional_signal") or ""
            ).upper()
            for label in [
                "BUYING",
                "ACCUMULATION",
                "BREAKOUT",
            ]
        )
    )

    low_risk_count = sum(
        1
        for item in profiles
        if item.get("risk_level") == "LOW"
    )

    sufficient_history_count = sum(
        1
        for item in profiles
        if item.get("risk_history_status")
        == "SUFFICIENT"
    )

    return {
        "total_profiles": total,
        "prediction_count":
            len(prediction_profiles),
        "strong_buy_count":
            strong_buy_count,
        "buy_count":
            buy_count,
        "hold_count":
            hold_count,
        "watch_count":
            watch_count,
        "avoid_count":
            avoid_count,
        "institutional_buying_count":
            institutional_buying_count,
        "low_risk_count":
            low_risk_count,
        "sufficient_history_count":
            sufficient_history_count,
        "average_confidence":
            average_confidence,
        "average_conviction":
            average_conviction,
        "average_expected_return":
            average_expected_return,
        "highest_conviction_symbol":
            highest_conviction.get("symbol"),
        "highest_conviction_score":
            highest_conviction.get(
                "conviction_score",
                0,
            ),
        "best_return_symbol":
            best_expected_return.get("symbol"),
        "best_expected_return":
            best_expected_return.get(
                "expected_return",
                0,
            ),
    }


def build_prediction_center() -> Dict[str, Any]:
    """
    Build the unified Prediction Center payload.

    This is the single integration point for:
    - live market data
    - technical analysis
    - predictive intelligence
    - market risk
    - screener intelligence
    - institutional volume intelligence
    - learning intelligence
    - unified AI conviction profiles
    """

    market = get_market_snapshot()
    stocks = market.get("stocks", [])

    technicals = analyze_market(stocks)

    predictions = build_predictions(
        stocks,
        technicals,
    )

    market_risk = build_market_risk(stocks)
    risk_rows = market_risk.get("stocks", [])

    breadth = get_market_breadth()

    learning = get_learning_summary(
        evaluate_first=False
    )

    market_regime = build_market_regime(
        breadth=breadth,
        predictions=predictions,
        institutional_rows=breadth.get(
            "volume_leaders",
            [],
        ),
        market_risk=market_risk,
        learning=learning,
    )

    screener_rows = run_screener()

    profiles = build_conviction_profiles(
        screener_rows=screener_rows,
        institutional_rows=breadth.get(
            "volume_leaders",
            [],
        ),
        prediction_rows=predictions,
        risk_rows=risk_rows,
        learning=learning,
        breadth=breadth,
        market_regime=market_regime,
    )

    prediction_symbols = {
        _normalise_symbol(
            item.get("symbol")
        )
        for item in predictions
        if item.get("symbol")
    }

    profiles = [
        {
            **item,
            "symbol": _normalise_symbol(
                item.get("symbol")
            ),
            "has_prediction": (
                _normalise_symbol(
                    item.get("symbol")
                )
                in prediction_symbols
            ),
            "conviction_score": _safe_int(
                item.get("conviction_score")
            ),
            "confidence": _safe_int(
                item.get("confidence")
            ),
            "expected_return": round(
                _safe_float(
                    item.get("expected_return")
                ),
                2,
            ),
            "target_price": round(
                _safe_float(
                    item.get("target_price")
                ),
                2,
            ),
            "prediction_probability_pct": round(
                _safe_float(
                    item.get(
                        "prediction_probability_pct"
                    )
                ),
                2,
            ),
            "relative_volume": round(
                _safe_float(
                    item.get("relative_volume")
                ),
                2,
            ),
            "volatility_pct": round(
                _safe_float(
                    item.get("volatility_pct")
                ),
                2,
            ),
            "maximum_drawdown_pct": round(
                _safe_float(
                    item.get(
                        "maximum_drawdown_pct"
                    )
                ),
                2,
            ),
        }
        for item in profiles
    ]

    prediction_profiles = [
        item
        for item in profiles
        if item.get("has_prediction", False)
    ]

    return {
        "version":
            "11.6.4 RC3 Prediction Center 2.0",
        "generated_at": datetime.now(
            KENYA_TIMEZONE
        ).isoformat(),
        "timezone": "Africa/Nairobi",
        "market_source": market.get(
            "source",
            "MyStocks Africa",
        ),
        "market_status": market.get("status"),
        "stock_count": len(stocks),
        "technical_count": len(technicals),
        "prediction_count":
            len(predictions),
        "risk_market_summary":
            market_risk,
        "breadth": {
            "advancers":
                breadth.get("advancers", 0),
            "decliners":
                breadth.get("decliners", 0),
            "unchanged":
                breadth.get("unchanged", 0),
            "advance_decline_ratio":
                breadth.get(
                    "advance_decline_ratio",
                    0,
                ),
            "breadth_signal":
                breadth.get("breadth_signal"),
            "market_pulse":
                breadth.get("market_pulse"),
        },
        "market_regime": market_regime,
        "learning": {
            "status":
                learning.get("status"),
            "accuracy":
                learning.get("accuracy"),
            "learning_score":
                learning.get("learning_score"),
            "learning_phase":
                learning.get("learning_phase"),
            "confidence_adjustment":
                learning.get(
                    "confidence_adjustment"
                ),
            "evaluations":
                learning.get("evaluations"),
        },
        "summary": _build_summary(profiles),
        "predictions": prediction_profiles,
        "all_profiles": profiles,
    }
