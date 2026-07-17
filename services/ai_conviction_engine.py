from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


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


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, value))


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalise_risk(value: Any) -> str:
    text = _upper(value)

    if "INSUFFICIENT" in text:
        return "INSUFFICIENT HISTORY"

    if "LOW" in text:
        return "LOW"

    if "HIGH" in text:
        return "HIGH"

    if "MEDIUM" in text or "MODERATE" in text:
        return "MEDIUM"

    return "INSUFFICIENT HISTORY"


def _risk_points(risk: str) -> float:
    return {
        "LOW": 10.0,
        "MEDIUM": 6.0,
        "HIGH": 2.0,
        "INSUFFICIENT HISTORY": 4.0,
    }.get(risk, 4.0)


def _decision_points(decision: Any) -> float:
    text = _upper(decision)

    return {
        "STRONG BUY": 15.0,
        "BUY": 12.0,
        "HOLD": 8.0,
        "WATCH": 6.0,
        "SELL": 2.0,
        "STRONG SELL": 0.0,
    }.get(text, 6.0)


def _trend_points(trend: Any) -> float:
    text = _upper(trend)

    if text in {"UPTREND", "STRONG BULLISH", "VERY BULLISH"}:
        return 10.0

    if "BULL" in text or text in {"POSITIVE", "RISING"}:
        return 8.0

    if text in {"NEUTRAL", "SIDEWAYS", ""}:
        return 5.0

    if "BEAR" in text or text in {"NEGATIVE", "FALLING"}:
        return 2.0

    return 5.0


def _rsi_points(rsi: float) -> float:
    if 50 <= rsi <= 65:
        return 5.0

    if 40 <= rsi < 50 or 65 < rsi <= 72:
        return 4.0

    if 30 <= rsi < 40 or 72 < rsi <= 78:
        return 2.0

    return 1.0


def _macd_points(macd: float) -> float:
    if macd > 0:
        return 5.0

    if macd == 0:
        return 3.0

    return 1.0


def _prediction_points(expected_return: float) -> float:
    if expected_return >= 15:
        return 10.0

    if expected_return >= 8:
        return 8.0

    if expected_return >= 3:
        return 6.0

    if expected_return >= 0:
        return 4.0

    return 0.0


def _rating(score: int) -> str:
    if score >= 90:
        return "★★★★★"

    if score >= 80:
        return "★★★★☆"

    if score >= 65:
        return "★★★☆☆"

    if score >= 50:
        return "★★☆☆☆"

    return "★☆☆☆☆"


def _signal(score: int) -> str:
    if score >= 90:
        return "STRONG BUY"

    if score >= 78:
        return "BUY"

    if score >= 62:
        return "HOLD"

    if score >= 48:
        return "WATCH"

    return "AVOID"


def _horizon(expected_return: float) -> str:
    if expected_return >= 15:
        return "1 Week"

    if expected_return >= 8:
        return "3–5 Days"

    if expected_return >= 3:
        return "1–3 Days"

    return "Monitor"


def _merge_reasons(
    *reason_groups: Iterable[str],
) -> List[str]:
    merged: List[str] = []

    for group in reason_groups:
        for reason in group or []:
            text = str(reason or "").strip()

            if text and text not in merged:
                merged.append(text)

    return merged[:6]


def build_conviction_profile(
    screener: Dict[str, Any],
    institutional: Optional[Dict[str, Any]] = None,
    prediction: Optional[Dict[str, Any]] = None,
    risk_metrics: Optional[Dict[str, Any]] = None,
    learning: Optional[Dict[str, Any]] = None,
    breadth: Optional[Dict[str, Any]] = None,
    market_regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    institutional = institutional or {}
    prediction = prediction or {}
    risk_metrics = risk_metrics or {}
    learning = learning or {}
    breadth = breadth or {}
    market_regime = market_regime or {}

    symbol = _upper(
        screener.get("symbol")
        or institutional.get("symbol")
        or prediction.get("symbol")
    )

    screener_confidence = _safe_float(
        screener.get("confidence"),
        50.0,
    )

    institutional_confidence = _safe_float(
        institutional.get(
            "institutional_confidence"
        ),
        50.0,
    )

    expected_return = _safe_float(
        prediction.get("expected_return_pct"),
        _safe_float(
            prediction.get("expected_return"),
            0.0,
        ),
    )

    prediction_probability = _safe_float(
        prediction.get("probability_success_pct"),
        _safe_float(
            prediction.get("probability"),
            _safe_float(
                prediction.get("confidence"),
                50.0,
            ),
        ),
    )

    learning_accuracy = _safe_float(
        learning.get("accuracy"),
        50.0,
    )

    learning_adjustment = _safe_float(
        learning.get("confidence_adjustment"),
        0.0,
    )

    risk = _normalise_risk(
        risk_metrics.get("risk")
        or risk_metrics.get("risk_level")
        or screener.get("risk")
    )

    trend = (
        screener.get("trend")
        or institutional.get("trend")
        or "Neutral"
    )

    rsi = _safe_float(screener.get("rsi"), 50.0)
    macd = _safe_float(screener.get("macd"), 0.0)

    advancing_percentage = _safe_float(
        breadth.get("advancing_percentage"),
        50.0,
    )

    breadth_points = (
        5.0
        if advancing_percentage >= 55
        else 3.0
        if advancing_percentage >= 45
        else 1.0
    )

    components = {
        "screener_points": round(
            _clamp(screener_confidence) * 0.25,
            2,
        ),
        "institutional_points": round(
            _clamp(institutional_confidence) * 0.20,
            2,
        ),
        "decision_points": _decision_points(
            screener.get("decision")
        ),
        "trend_points": _trend_points(trend),
        "rsi_points": _rsi_points(rsi),
        "macd_points": _macd_points(macd),
        "prediction_points": _prediction_points(
            expected_return
        ),
        "risk_points": _risk_points(risk),
        "learning_points": round(
            _clamp(learning_accuracy) * 0.05,
            2,
        ),
        "breadth_points": breadth_points,
    }

    raw_score = sum(components.values())

    raw_score += min(
        max(learning_adjustment, -5.0),
        5.0,
    )

    raw_conviction_score = _safe_int(
        _clamp(raw_score)
    )

    regime_multiplier = _safe_float(
        market_regime.get(
            "conviction_multiplier"
        ),
        1.0,
    )

    regime_adjusted_conviction_score = _safe_int(
        _clamp(
            raw_conviction_score
            * regime_multiplier
        )
    )

    conviction_score = (
        regime_adjusted_conviction_score
    )

    confidence = _safe_int(
        _clamp(
            (
                screener_confidence * 0.45
                + institutional_confidence * 0.30
                + prediction_probability * 0.25
            )
            + learning_adjustment
        )
    )

    reasons = _merge_reasons(
        screener.get("reasons") or [],
        institutional.get(
            "institutional_reasons"
        ) or [],
        prediction.get("reasons") or [],
    )

    institutional_signal = (
        institutional.get(
            "institutional_signal"
        )
        or institutional.get("signal")
        or "No strong institutional signal"
    )

    target_price = _safe_float(
        prediction.get("target_price"),
        _safe_float(
            prediction.get("target"),
            0.0,
        ),
    )

    result = {
        "symbol": symbol,
        "name": (
            screener.get("name")
            or institutional.get("name")
            or symbol
        ),
        "price": _safe_float(
            screener.get("price"),
            _safe_float(
                institutional.get("price"),
                0.0,
            ),
        ),
        "raw_conviction_score":
            raw_conviction_score,
        "regime_adjusted_conviction_score":
            regime_adjusted_conviction_score,
        "conviction_score": conviction_score,
        "rating": _rating(conviction_score),
        "signal": _signal(conviction_score),
        "market_regime":
            market_regime.get("regime"),
        "market_regime_badge":
            market_regime.get("badge"),
        "regime_multiplier":
            regime_multiplier,
        "confidence": confidence,
        "risk": risk,
        "risk_level": risk,
        "horizon": (
            f"{_safe_int(prediction.get('holding_period_days'))} Days"
            if _safe_int(
                prediction.get("holding_period_days")
            ) > 0
            else _horizon(expected_return)
        ),
        "holding_period_days": _safe_int(
            prediction.get("holding_period_days"),
            0,
        ),
        "expected_return": round(
            expected_return,
            2,
        ),
        "target_price": round(
            target_price,
            2,
        ),
        "prediction_probability_pct": round(
            prediction_probability,
            2,
        ),
        "prediction_signal": (
            prediction.get("signal")
            or screener.get("decision")
            or "WATCH"
        ),
        "prediction_model_mode": prediction.get(
            "model_mode"
        ),
        "annualized_volatility_pct": round(
            _safe_float(
                prediction.get(
                    "annualized_volatility_pct"
                ),
                _safe_float(
                    risk_metrics.get(
                        "volatility_pct"
                    ),
                    0.0,
                ),
            ),
            2,
        ),
        "maximum_expected_drawdown_pct": round(
            _safe_float(
                prediction.get(
                    "maximum_expected_drawdown_pct"
                ),
                0.0,
            ),
            2,
        ),
        "volatility_pct": round(
            _safe_float(
                risk_metrics.get("volatility_pct"),
                _safe_float(
                    prediction.get(
                        "annualized_volatility_pct"
                    ),
                    0.0,
                ),
            ),
            2,
        ),
        "maximum_drawdown_pct": round(
            _safe_float(
                risk_metrics.get(
                    "maximum_drawdown_pct"
                ),
                _safe_float(
                    prediction.get(
                        "maximum_expected_drawdown_pct"
                    ),
                    0.0,
                ),
            ),
            2,
        ),
        "var_95_pct": round(
            _safe_float(
                risk_metrics.get("var_95_pct"),
                0.0,
            ),
            2,
        ),
        "cvar_95_pct": round(
            _safe_float(
                risk_metrics.get("cvar_95_pct"),
                0.0,
            ),
            2,
        ),
        "sharpe_ratio": round(
            _safe_float(
                risk_metrics.get("sharpe_ratio"),
                0.0,
            ),
            2,
        ),
        "sortino_ratio": round(
            _safe_float(
                risk_metrics.get("sortino_ratio"),
                0.0,
            ),
            2,
        ),
        "risk_history_rows": _safe_int(
            risk_metrics.get("history_rows"),
            0,
        ),
        "risk_history_status": (
            "SUFFICIENT"
            if _safe_int(
                risk_metrics.get("history_rows")
            ) >= 30
            else "INSUFFICIENT HISTORY"
        ),
        "decision": screener.get(
            "decision",
            "WATCH",
        ),
        "institutional_signal":
            institutional_signal,
        "institutional_confidence":
            _safe_int(
                institutional_confidence
            ),
        "relative_volume": round(
            _safe_float(
                institutional.get(
                    "relative_volume"
                ),
                0.0,
            ),
            2,
        ),
        "trend": trend,
        "rsi": round(rsi, 2),
        "macd": round(macd, 3),
        "reasons": reasons,
        "score_components": components,
        "learning_accuracy": round(
            learning_accuracy,
            2,
        ),
        "market_breadth_signal":
            breadth.get("breadth_signal"),
    }

    return result


def build_conviction_profiles(
    screener_rows: List[Dict[str, Any]],
    institutional_rows: Optional[
        List[Dict[str, Any]]
    ] = None,
    prediction_rows: Optional[
        List[Dict[str, Any]]
    ] = None,
    risk_rows: Optional[
        List[Dict[str, Any]]
    ] = None,
    learning: Optional[Dict[str, Any]] = None,
    breadth: Optional[Dict[str, Any]] = None,
    market_regime: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    institutional_map = {
        _upper(item.get("symbol")): item
        for item in (institutional_rows or [])
    }

    prediction_map = {
        _upper(item.get("symbol")): item
        for item in (prediction_rows or [])
    }

    risk_map = {
        _upper(item.get("symbol")): item
        for item in (risk_rows or [])
    }

    profiles = [
        build_conviction_profile(
            screener=item,
            institutional=institutional_map.get(
                _upper(item.get("symbol"))
            ),
            prediction=prediction_map.get(
                _upper(item.get("symbol"))
            ),
            risk_metrics=risk_map.get(
                _upper(item.get("symbol"))
            ),
            learning=learning,
            breadth=breadth,
            market_regime=market_regime,
        )
        for item in screener_rows
    ]

    return sorted(
        profiles,
        key=lambda item: (
            item["conviction_score"],
            item["confidence"],
        ),
        reverse=True,
    )
