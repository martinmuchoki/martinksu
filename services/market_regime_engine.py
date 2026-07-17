from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo


KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, value))


def _average(
    values: Iterable[float],
    default: float = 0.0,
) -> float:
    cleaned = [
        float(value)
        for value in values
        if value is not None
    ]

    if not cleaned:
        return default

    return sum(cleaned) / len(cleaned)


def _prediction_signal_score(
    predictions: List[Dict[str, Any]],
) -> float:
    if not predictions:
        return 50.0

    weights = {
        "STRONG BUY": 100.0,
        "BUY": 82.0,
        "HOLD": 55.0,
        "WATCH": 38.0,
        "AVOID": 10.0,
        "SELL": 10.0,
        "STRONG SELL": 0.0,
    }

    values = [
        weights.get(
            str(item.get("signal") or "")
            .strip()
            .upper(),
            50.0,
        )
        for item in predictions
    ]

    return _average(values, 50.0)


def _prediction_return_score(
    predictions: List[Dict[str, Any]],
) -> float:
    if not predictions:
        return 50.0

    average_return = _average(
        [
            _safe_float(
                item.get(
                    "expected_return",
                    item.get("expected_return_pct"),
                )
            )
            for item in predictions
        ],
        0.0,
    )

    # Maps approximately -10% to 0 and +15% to 100.
    return _clamp(
        40.0 + average_return * 4.0
    )


def _institutional_score(
    institutional_rows: List[Dict[str, Any]],
) -> float:
    if not institutional_rows:
        return 50.0

    positive_terms = (
        "BUYING",
        "ACCUMULATION",
        "BREAKOUT",
    )

    negative_terms = (
        "DISTRIBUTION",
        "SELLING",
        "EXIT",
    )

    scores: List[float] = []

    for item in institutional_rows:
        signal = str(
            item.get("institutional_signal")
            or item.get("signal")
            or ""
        ).upper()

        confidence = _safe_float(
            item.get(
                "institutional_confidence",
                item.get("confidence"),
            ),
            50.0,
        )

        if any(term in signal for term in positive_terms):
            scores.append(
                max(60.0, confidence)
            )
        elif any(term in signal for term in negative_terms):
            scores.append(
                min(35.0, 100.0 - confidence)
            )
        else:
            scores.append(50.0)

    return _average(scores, 50.0)


def _risk_score(
    market_risk: Optional[Dict[str, Any]],
) -> float:
    market_risk = market_risk or {}

    volatility = _safe_float(
        market_risk.get(
            "average_volatility_pct"
        ),
        50.0,
    )

    drawdown = abs(
        _safe_float(
            market_risk.get(
                "worst_drawdown_pct"
            ),
            20.0,
        )
    )

    risk_level = str(
        market_risk.get(
            "market_risk_level"
        )
        or ""
    ).upper()

    score = 75.0

    score -= min(
        volatility * 0.45,
        35.0,
    )

    score -= min(
        drawdown * 0.65,
        25.0,
    )

    if "HIGH" in risk_level:
        score -= 10.0
    elif "LOW" in risk_level:
        score += 8.0

    return _clamp(score)


def _classify_regime(
    regime_score: float,
    risk_score: float,
    advancing_percentage: float,
    institutional_score: float,
) -> str:
    if (
        risk_score < 28
        and regime_score < 55
    ):
        return "HIGH VOLATILITY"

    if (
        regime_score >= 75
        and advancing_percentage >= 55
    ):
        return "BULL MARKET"

    if (
        regime_score >= 60
        and advancing_percentage >= 48
    ):
        return "RECOVERY"

    if (
        institutional_score < 40
        and advancing_percentage < 45
    ):
        return "DISTRIBUTION"

    if regime_score < 38:
        return "BEAR MARKET"

    return "SIDEWAYS"


def _regime_badge(regime: str) -> str:
    return {
        "BULL MARKET": "🟢",
        "RECOVERY": "🔵",
        "SIDEWAYS": "🟡",
        "DISTRIBUTION": "🟠",
        "BEAR MARKET": "🔴",
        "HIGH VOLATILITY": "⚠️",
    }.get(regime, "⚪")


def _exposure_guidance(
    regime: str,
) -> Dict[str, int]:
    allocations = {
        "BULL MARKET": {
            "equities_pct": 80,
            "cash_pct": 20,
        },
        "RECOVERY": {
            "equities_pct": 70,
            "cash_pct": 30,
        },
        "SIDEWAYS": {
            "equities_pct": 55,
            "cash_pct": 45,
        },
        "DISTRIBUTION": {
            "equities_pct": 40,
            "cash_pct": 60,
        },
        "BEAR MARKET": {
            "equities_pct": 25,
            "cash_pct": 75,
        },
        "HIGH VOLATILITY": {
            "equities_pct": 35,
            "cash_pct": 65,
        },
    }

    return allocations.get(
        regime,
        {
            "equities_pct": 50,
            "cash_pct": 50,
        },
    )


def _conviction_multiplier(
    regime: str,
) -> float:
    return {
        "BULL MARKET": 1.08,
        "RECOVERY": 1.04,
        "SIDEWAYS": 0.98,
        "DISTRIBUTION": 0.90,
        "BEAR MARKET": 0.84,
        "HIGH VOLATILITY": 0.88,
    }.get(regime, 1.0)


def _build_reasons(
    advancing_percentage: float,
    declining_percentage: float,
    prediction_score: float,
    institutional_score: float,
    risk_score: float,
) -> List[str]:
    reasons: List[str] = []

    if advancing_percentage >= 55:
        reasons.append(
            "Broad market participation is positive"
        )
    elif declining_percentage >= 55:
        reasons.append(
            "Declining stocks dominate market breadth"
        )
    else:
        reasons.append(
            "Market participation remains mixed"
        )

    if prediction_score >= 65:
        reasons.append(
            "Unified predictions favour positive returns"
        )
    elif prediction_score < 40:
        reasons.append(
            "Prediction strength remains defensive"
        )

    if institutional_score >= 65:
        reasons.append(
            "Institutional accumulation is supportive"
        )
    elif institutional_score < 40:
        reasons.append(
            "Institutional flow suggests distribution"
        )

    if risk_score < 35:
        reasons.append(
            "Market volatility and drawdown risk are elevated"
        )
    elif risk_score >= 60:
        reasons.append(
            "Risk conditions are comparatively stable"
        )

    return reasons[:5]


def build_market_regime(
    breadth: Optional[Dict[str, Any]] = None,
    predictions: Optional[
        List[Dict[str, Any]]
    ] = None,
    institutional_rows: Optional[
        List[Dict[str, Any]]
    ] = None,
    market_risk: Optional[
        Dict[str, Any]
    ] = None,
    learning: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    breadth = breadth or {}
    predictions = predictions or []
    institutional_rows = institutional_rows or []
    market_risk = market_risk or {}
    learning = learning or {}

    advancing_percentage = _safe_float(
        breadth.get("advancing_percentage"),
        50.0,
    )

    declining_percentage = _safe_float(
        breadth.get("declining_percentage"),
        50.0,
    )

    breadth_score = _clamp(
        advancing_percentage
        + (
            advancing_percentage
            - declining_percentage
        ) * 0.50
    )

    prediction_signal_score = (
        _prediction_signal_score(predictions)
    )

    prediction_return_score = (
        _prediction_return_score(predictions)
    )

    prediction_score = _average(
        [
            prediction_signal_score,
            prediction_return_score,
        ],
        50.0,
    )

    institutional_score = (
        _institutional_score(
            institutional_rows
        )
    )

    risk_score = _risk_score(
        market_risk
    )

    learning_score = _safe_float(
        learning.get("learning_score"),
        50.0,
    )

    components = {
        "breadth_score": round(
            breadth_score,
            2,
        ),
        "prediction_score": round(
            prediction_score,
            2,
        ),
        "institutional_score": round(
            institutional_score,
            2,
        ),
        "risk_score": round(
            risk_score,
            2,
        ),
        "learning_score": round(
            learning_score,
            2,
        ),
    }

    regime_score = (
        breadth_score * 0.30
        + prediction_score * 0.25
        + institutional_score * 0.20
        + risk_score * 0.15
        + learning_score * 0.10
    )

    regime_score = _clamp(
        regime_score
    )

    regime = _classify_regime(
        regime_score=regime_score,
        risk_score=risk_score,
        advancing_percentage=advancing_percentage,
        institutional_score=institutional_score,
    )

    exposure = _exposure_guidance(regime)

    confidence = _clamp(
        50.0
        + abs(regime_score - 50.0) * 0.75
        + min(
            len(predictions),
            20,
        ) * 0.50
    )

    return {
        "version":
            "11.7 Institutional Regime Engine",
        "generated_at": datetime.now(
            KENYA_TIMEZONE
        ).isoformat(),
        "regime": regime,
        "badge": _regime_badge(regime),
        "regime_score": round(
            regime_score,
            2,
        ),
        "confidence": _safe_int(
            confidence
        ),
        "conviction_multiplier":
            _conviction_multiplier(regime),
        "recommended_equities_pct":
            exposure["equities_pct"],
        "recommended_cash_pct":
            exposure["cash_pct"],
        "advancing_percentage": round(
            advancing_percentage,
            2,
        ),
        "declining_percentage": round(
            declining_percentage,
            2,
        ),
        "market_risk_level":
            market_risk.get(
                "market_risk_level",
                "UNKNOWN",
            ),
        "components": components,
        "reasons": _build_reasons(
            advancing_percentage,
            declining_percentage,
            prediction_score,
            institutional_score,
            risk_score,
        ),
    }


def build_live_market_regime() -> Dict[str, Any]:
    """
    Build the regime from the active MIP PRO services.

    Imports are local to avoid circular imports during
    dashboard and API initialization.
    """

    from services.dashboard_charts import (
        get_market_breadth,
    )
    from services.learning_engine import (
        get_learning_summary,
    )
    from services.market_data import (
        get_market_snapshot,
    )
    from services.predictive_engine import (
        build_predictions,
    )
    from services.risk_engine import (
        build_market_risk,
    )
    from services.technical_analysis import (
        analyze_market,
    )

    market = get_market_snapshot()
    stocks = market.get("stocks", [])

    technicals = analyze_market(stocks)

    predictions = build_predictions(
        stocks,
        technicals,
    )

    breadth = get_market_breadth()

    market_risk = build_market_risk(
        stocks
    )

    learning = get_learning_summary(
        evaluate_first=False
    )

    return build_market_regime(
        breadth=breadth,
        predictions=predictions,
        institutional_rows=breadth.get(
            "volume_leaders",
            [],
        ),
        market_risk=market_risk,
        learning=learning,
    )
