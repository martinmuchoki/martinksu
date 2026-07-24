from __future__ import annotations

import math
from statistics import median, pstdev
from typing import Any, Dict, Iterable, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, value))


def _normal_cdf(value: float) -> float:
    """
    Deterministic standard-normal cumulative probability.
    """
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def calculate_volume_statistics(
    historical_volumes: Iterable[Any],
    current_volume: Any = 0,
) -> Dict[str, Any]:
    """
    Calculate deterministic rolling volume statistics.

    Zero or invalid historical observations are excluded because they usually
    represent unavailable source data rather than genuine zero trading.
    """
    values: List[int] = [
        _safe_int(value)
        for value in historical_volumes
        if _safe_int(value) > 0
    ]

    current = max(0, _safe_int(current_volume))

    if not values:
        fallback = current if current > 0 else 0

        return {
            "history_count": 0,
            "average_volume_20d": fallback,
            "median_volume_20d": fallback,
            "volume_std_dev_20d": 0.0,
            "maximum_volume_20d": fallback,
            "minimum_volume_20d": fallback,
            "relative_volume": 1.0 if fallback > 0 else 0.0,
            "volume_z_score": 0.0,
            "volume_percentile": 50.0 if fallback > 0 else 0.0,
            "abnormal_volume_probability": 0.0,
            "statistics_reliability": "INSUFFICIENT_HISTORY",
        }

    average = sum(values) / len(values)
    median_value = median(values)
    std_dev = pstdev(values) if len(values) >= 2 else 0.0

    relative_volume = (
        current / average
        if current > 0 and average > 0
        else 0.0
    )

    z_score = (
        (current - average) / std_dev
        if current > 0 and std_dev > 0
        else 0.0
    )

    less_or_equal = sum(1 for value in values if value <= current)
    percentile = (less_or_equal / len(values)) * 100.0

    abnormal_probability = (
        _normal_cdf(abs(z_score)) * 100.0
        if std_dev > 0
        else 0.0
    )

    if len(values) >= 15:
        reliability = "HIGH"
    elif len(values) >= 7:
        reliability = "MEDIUM"
    else:
        reliability = "LOW"

    return {
        "history_count": len(values),
        "average_volume_20d": round(average),
        "median_volume_20d": round(median_value),
        "volume_std_dev_20d": round(std_dev, 2),
        "maximum_volume_20d": max(values),
        "minimum_volume_20d": min(values),
        "relative_volume": round(relative_volume, 2),
        "volume_z_score": round(z_score, 2),
        "volume_percentile": round(percentile, 2),
        "abnormal_volume_probability": round(
            _clamp(abnormal_probability),
            2,
        ),
        "statistics_reliability": reliability,
    }


def calculate_liquidity_score(stock: Dict[str, Any]) -> int:
    """
    Estimate practical liquidity from traded volume and traded value.

    This remains deterministic and deliberately avoids market-cap assumptions
    because provider market-cap units are not yet fully normalized.
    """
    volume = max(0, _safe_int(stock.get("volume")))
    price = max(0.0, _safe_float(stock.get("price")))

    traded_value = _safe_float(stock.get("value"))

    if traded_value <= 0 and volume > 0 and price > 0:
        traded_value = volume * price

    volume_points = min(
        55.0,
        math.log10(volume + 1) / 7.0 * 55.0,
    )

    value_points = min(
        45.0,
        math.log10(traded_value + 1) / 9.0 * 45.0,
    )

    return round(_clamp(volume_points + value_points))


def calculate_institutional_probability(
    stock: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce deterministic accumulation and distribution probabilities.
    """
    rvol = max(
        0.0,
        _safe_float(stock.get("relative_volume"), 1.0),
    )
    z_score = _safe_float(stock.get("volume_z_score"))
    percentile = _clamp(
        _safe_float(stock.get("volume_percentile"), 50.0)
    )
    liquidity = _clamp(
        _safe_float(stock.get("liquidity_score"))
    )
    ai_score = _clamp(
        _safe_float(
            stock.get("ai_score", stock.get("score", 50.0)),
            50.0,
        )
    )
    change = _safe_float(
        stock.get("change_pct", stock.get("change_percent", 0.0))
    )

    trend = str(stock.get("trend") or "Neutral").strip().lower()

    volume_strength = _clamp(
        min(rvol / 4.0, 1.0) * 45.0
        + min(max(z_score, 0.0) / 3.0, 1.0) * 25.0
        + percentile / 100.0 * 30.0
    )

    positive_price_confirmation = _clamp(
        50.0 + change * 10.0
    )
    negative_price_confirmation = _clamp(
        50.0 - change * 10.0
    )

    bullish_trend = (
        100.0 if trend == "bullish"
        else 30.0 if trend == "bearish"
        else 55.0
    )

    bearish_trend = (
        100.0 if trend == "bearish"
        else 30.0 if trend == "bullish"
        else 55.0
    )

    accumulation_probability = (
        volume_strength * 0.32
        + positive_price_confirmation * 0.23
        + liquidity * 0.15
        + ai_score * 0.20
        + bullish_trend * 0.10
    )

    distribution_probability = (
        volume_strength * 0.37
        + negative_price_confirmation * 0.28
        + liquidity * 0.15
        + (100.0 - ai_score) * 0.10
        + bearish_trend * 0.10
    )

    return {
        "institutional_probability": round(
            _clamp(accumulation_probability),
            2,
        ),
        "distribution_probability": round(
            _clamp(distribution_probability),
            2,
        ),
        "volume_strength_score": round(volume_strength, 2),
    }


def _classification(
    accumulation_probability: float,
    distribution_probability: float,
    liquidity_score: float,
    relative_volume: float,
) -> Dict[str, str]:
    strongest = max(
        accumulation_probability,
        distribution_probability,
    )

    if liquidity_score < 25 and relative_volume < 1.5:
        return {
            "signal": "Retail Dominated",
            "badge": "🔴",
            "signal_class": "weak",
        }

    if distribution_probability >= 78:
        return {
            "signal": "Active Distribution",
            "badge": "🔴",
            "signal_class": "distribution",
        }

    if distribution_probability >= 65:
        return {
            "signal": "Possible Institutional Exit",
            "badge": "🟠",
            "signal_class": "distribution",
        }

    if accumulation_probability >= 80:
        return {
            "signal": "Strong Institutional Accumulation",
            "badge": "🔥",
            "signal_class": "strong-accumulation",
        }

    if accumulation_probability >= 68:
        return {
            "signal": "Early Institutional Accumulation",
            "badge": "🟢",
            "signal_class": "accumulation",
        }

    if strongest >= 55:
        return {
            "signal": "Neutral Participation",
            "badge": "⚪",
            "signal_class": "watchlist",
        }

    return {
        "signal": "Weak Participation",
        "badge": "🔴",
        "signal_class": "weak",
    }


def _build_reasons(stock: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []

    rvol = _safe_float(stock.get("relative_volume"))
    z_score = _safe_float(stock.get("volume_z_score"))
    percentile = _safe_float(stock.get("volume_percentile"))
    liquidity = _safe_float(stock.get("liquidity_score"))
    change = _safe_float(
        stock.get("change_pct", stock.get("change_percent"))
    )
    reliability = str(
        stock.get("statistics_reliability") or ""
    )

    if rvol >= 3:
        reasons.append(f"Relative volume {rvol:.2f}× normal")
    elif rvol >= 1.5:
        reasons.append(f"Above-average volume at {rvol:.2f}×")

    if z_score >= 2:
        reasons.append(f"Statistically unusual volume, z-score {z_score:.2f}")

    if percentile >= 90:
        reasons.append(f"Volume exceeds {percentile:.0f}% of recent sessions")

    if liquidity >= 75:
        reasons.append("High execution liquidity")
    elif liquidity < 30:
        reasons.append("Limited execution liquidity")

    if change >= 2:
        reasons.append("Strong positive price confirmation")
    elif change > 0:
        reasons.append("Positive price confirmation")
    elif change <= -2:
        reasons.append("Strong negative price confirmation")
    elif change < 0:
        reasons.append("Negative price confirmation")

    if reliability in {"LOW", "INSUFFICIENT_HISTORY"}:
        reasons.append("Historical confidence is limited")

    if not reasons:
        reasons.append("Normal volume participation")

    return reasons[:6]


def classify_stock(stock: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a backward-compatible institutional trading profile.

    Existing fields are retained:
    confidence, badge, signal and momentum.

    New enterprise metrics are added when historical data is available.
    """
    result = dict(stock)

    current_volume = max(0, _safe_int(result.get("volume")))

    historical_volumes = result.get("historical_volumes")

    if isinstance(historical_volumes, (list, tuple)):
        statistics = calculate_volume_statistics(
            historical_volumes,
            current_volume,
        )
        result.update(statistics)
    else:
        result.setdefault(
            "relative_volume",
            round(
                max(
                    0.0,
                    _safe_float(result.get("relative_volume"), 1.0),
                ),
                2,
            ),
        )
        result.setdefault("volume_z_score", 0.0)
        result.setdefault("volume_percentile", 50.0)
        result.setdefault("abnormal_volume_probability", 0.0)
        result.setdefault("median_volume_20d", 0)
        result.setdefault("volume_std_dev_20d", 0.0)
        result.setdefault("maximum_volume_20d", 0)
        result.setdefault("minimum_volume_20d", 0)
        result.setdefault("history_count", 0)
        result.setdefault(
            "statistics_reliability",
            "LEGACY_BASELINE",
        )

    liquidity_score = calculate_liquidity_score(result)
    result["liquidity_score"] = liquidity_score

    probabilities = calculate_institutional_probability(result)
    result.update(probabilities)

    classification = _classification(
        probabilities["institutional_probability"],
        probabilities["distribution_probability"],
        liquidity_score,
        _safe_float(result.get("relative_volume")),
    )

    change = _safe_float(
        result.get("change_pct", result.get("change_percent"))
    )

    if change >= 5:
        momentum = "Very Strong"
    elif change >= 2:
        momentum = "Strong"
    elif change <= -2:
        momentum = "Weak"
    else:
        momentum = "Normal"

    confidence = round(
        _clamp(
            max(
                probabilities["institutional_probability"],
                probabilities["distribution_probability"],
            )
        )
    )

    reasons = _build_reasons(result)

    result.update(
        {
            "confidence": confidence,
            "institutional_confidence": confidence,
            "badge": classification["badge"],
            "institutional_badge": classification["badge"],
            "signal": classification["signal"],
            "institutional_signal": classification["signal"],
            "signal_class": classification["signal_class"],
            "momentum": momentum,
            "institutional_reasons": reasons,
            "explanation": reasons,
        }
    )

    return result
