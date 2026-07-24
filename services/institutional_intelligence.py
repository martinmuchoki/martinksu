from __future__ import annotations

from typing import Any, Dict, List


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
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, value))


def _normalise_text(value: Any) -> str:
    return str(value or "").strip().upper()


def _trend_points(trend: Any) -> float:
    text = _normalise_text(trend)

    if text in {
        "STRONG BULLISH",
        "VERY BULLISH",
        "UPTREND",
    }:
        return 10.0

    if text in {
        "BULLISH",
        "POSITIVE",
        "RISING",
    }:
        return 8.0

    if text in {
        "WEAK BULLISH",
        "SLIGHTLY BULLISH",
    }:
        return 6.0

    if text in {
        "BEARISH",
        "NEGATIVE",
        "FALLING",
    }:
        return 2.0

    if text in {
        "STRONG BEARISH",
        "VERY BEARISH",
        "DOWNTREND",
    }:
        return 0.0

    return 5.0


def _momentum_points(
    momentum: Any,
    change_pct: float,
) -> float:
    text = _normalise_text(momentum)

    if text in {
        "VERY STRONG",
        "STRONG BULLISH",
    }:
        return 10.0

    if text in {
        "STRONG",
        "BULLISH",
        "POSITIVE",
    }:
        return 8.0

    if text in {
        "MODERATE",
        "IMPROVING",
    }:
        return 6.0

    if text in {
        "WEAK",
        "BEARISH",
        "NEGATIVE",
    }:
        return 2.0

    if change_pct >= 5:
        return 10.0

    if change_pct >= 2:
        return 8.0

    if change_pct > 0:
        return 6.0

    if change_pct <= -5:
        return 0.0

    if change_pct <= -2:
        return 2.0

    return 5.0


def _rvol_points(relative_volume: float) -> float:
    if relative_volume >= 10:
        return 20.0

    if relative_volume >= 5:
        return 18.0

    if relative_volume >= 3:
        return 15.0

    if relative_volume >= 2:
        return 12.0

    if relative_volume >= 1.5:
        return 9.0

    if relative_volume >= 1:
        return 6.0

    if relative_volume >= 0.5:
        return 3.0

    return 0.0


def _liquidity_points(volume: int) -> float:
    if volume >= 1_500_000:
        return 5.0

    if volume >= 1_000_000:
        return 4.5

    if volume >= 500_000:
        return 4.0

    if volume >= 200_000:
        return 3.0

    if volume >= 50_000:
        return 2.0

    if volume > 0:
        return 1.0

    return 0.0


def _price_change_points(change_pct: float) -> float:
    if change_pct >= 5:
        return 5.0

    if change_pct >= 2:
        return 4.0

    if change_pct > 0:
        return 3.0

    if change_pct == 0:
        return 2.0

    if change_pct > -2:
        return 1.0

    return 0.0


def _breadth_points(
    change_pct: float,
    advancing_percentage: float,
) -> float:
    if advancing_percentage >= 60 and change_pct > 0:
        return 5.0

    if advancing_percentage >= 50 and change_pct >= 0:
        return 4.0

    if advancing_percentage >= 40:
        return 3.0

    if change_pct > 0:
        return 2.0

    return 1.0


def _volume_rank_points(rank: int) -> float:
    if rank <= 3:
        return 5.0

    if rank <= 5:
        return 4.0

    if rank <= 10:
        return 3.0

    if rank <= 16:
        return 2.0

    return 0.0


def _classification(
    confidence: int,
) -> Dict[str, str]:
    if confidence >= 95:
        return {
            "badge": "🔥",
            "signal": (
                "Exceptional Institutional Breakout"
            ),
            "signal_class": "exceptional",
        }

    if confidence >= 85:
        return {
            "badge": "🟢",
            "signal": "Institutional Buying",
            "signal_class": "buying",
        }

    if confidence >= 75:
        return {
            "badge": "🟢",
            "signal": "Strong Accumulation",
            "signal_class": "strong-accumulation",
        }

    if confidence >= 65:
        return {
            "badge": "🟡",
            "signal": "Accumulation",
            "signal_class": "accumulation",
        }

    if confidence >= 50:
        return {
            "badge": "⚪",
            "signal": "Watchlist",
            "signal_class": "watchlist",
        }

    return {
        "badge": "🔴",
        "signal": "Weak Participation",
        "signal_class": "weak",
    }


def _build_reasons(
    ai_score: float,
    relative_volume: float,
    trend: Any,
    momentum: Any,
    change_pct: float,
    volume_rank: int,
    volume: int,
) -> List[str]:
    reasons: List[str] = []

    if ai_score >= 85:
        reasons.append("Exceptional AI ranking")
    elif ai_score >= 75:
        reasons.append("Strong AI ranking")
    elif ai_score >= 65:
        reasons.append("Positive AI ranking")

    if relative_volume >= 10:
        reasons.append("Exceptional relative volume")
    elif relative_volume >= 5:
        reasons.append("Very high relative volume")
    elif relative_volume >= 2:
        reasons.append("Above-average participation")

    trend_text = _normalise_text(trend)

    if "BULL" in trend_text or trend_text in {
        "UPTREND",
        "RISING",
        "POSITIVE",
    }:
        reasons.append("Bullish technical trend")

    momentum_text = _normalise_text(momentum)

    if momentum_text in {
        "VERY STRONG",
        "STRONG",
        "BULLISH",
        "POSITIVE",
    } or change_pct >= 2:
        reasons.append("Strong positive momentum")

    if volume_rank <= 5:
        reasons.append("Top-five volume leader")
    elif volume_rank <= 10:
        reasons.append("Top-ten volume leader")

    if volume >= 1_000_000:
        reasons.append("High market liquidity")

    if change_pct < 0:
        reasons.append(
            "Price confirmation remains weak"
        )

    if not reasons:
        reasons.append(
            "Activity requires further confirmation"
        )

    return reasons[:4]


def build_institutional_profile(
    stock: Dict[str, Any],
    volume_rank: int = 99,
    advancing_percentage: float = 50.0,
) -> Dict[str, Any]:
    """
    Add market context and presentation metadata.

    Canonical institutional analytics are owned by
    services.institutional_volume.classify_stock().

    This function must not overwrite statistical decisions already
    present in the stock profile.
    """
    result = dict(stock)

    ai_score = _safe_float(
        result.get("score"),
        _safe_float(
            result.get("ai_score"),
            50.0,
        ),
    )

    relative_volume = _safe_float(
        result.get("relative_volume"),
        0.0,
    )

    volume = _safe_int(
        result.get("volume"),
        0,
    )

    change_pct = _safe_float(
        result.get("change_pct"),
        _safe_float(
            result.get("change_percent"),
            0.0,
        ),
    )

    trend = result.get("trend") or "Neutral"
    momentum = result.get("momentum") or "Normal"

    safe_volume_rank = _safe_int(
        volume_rank,
        99,
    )

    if safe_volume_rank <= 0:
        safe_volume_rank = 99

    safe_advancing_percentage = _clamp(
        _safe_float(
            advancing_percentage,
            50.0,
        )
    )

    presentation_components = {
        "ai_score_points": round(
            _clamp(ai_score) * 0.40,
            2,
        ),
        "rvol_points": _rvol_points(
            relative_volume
        ),
        "trend_points": _trend_points(
            trend
        ),
        "momentum_points": _momentum_points(
            momentum,
            change_pct,
        ),
        "liquidity_points": _liquidity_points(
            volume
        ),
        "price_change_points": (
            _price_change_points(
                change_pct
            )
        ),
        "market_breadth_points": (
            _breadth_points(
                change_pct,
                safe_advancing_percentage,
            )
        ),
        "volume_rank_points": (
            _volume_rank_points(
                safe_volume_rank
            )
        ),
    }

    presentation_score = round(
        _clamp(
            sum(
                presentation_components.values()
            )
        )
    )

    result["volume_rank"] = safe_volume_rank

    result["market_advancing_percentage"] = round(
        safe_advancing_percentage,
        2,
    )

    result["presentation_score"] = (
        presentation_score
    )

    result["presentation_score_components"] = (
        presentation_components
    )

    result["market_breadth_points"] = (
        presentation_components[
            "market_breadth_points"
        ]
    )

    result["volume_rank_points"] = (
        presentation_components[
            "volume_rank_points"
        ]
    )

    # Backward compatibility only.
    result.setdefault(
        "score_components",
        presentation_components,
    )

    # Fallbacks apply only when classify_stock() was bypassed.
    canonical_confidence = result.get(
        "institutional_confidence"
    )

    if canonical_confidence is None:
        canonical_confidence = result.get(
            "confidence"
        )

    if canonical_confidence is None:
        canonical_confidence = presentation_score

    result.setdefault(
        "institutional_confidence",
        canonical_confidence,
    )

    result.setdefault(
        "confidence",
        canonical_confidence,
    )

    canonical_signal = result.get(
        "institutional_signal"
    )

    if not canonical_signal:
        canonical_signal = result.get(
            "signal"
        )

    fallback_classification = None

    if not canonical_signal:
        fallback_classification = _classification(
            presentation_score
        )

        canonical_signal = (
            fallback_classification["signal"]
        )

    result.setdefault(
        "institutional_signal",
        canonical_signal,
    )

    result.setdefault(
        "signal",
        canonical_signal,
    )

    canonical_badge = result.get(
        "institutional_badge"
    )

    if not canonical_badge:
        canonical_badge = result.get(
            "badge"
        )

    if (
        not canonical_badge
        and fallback_classification
    ):
        canonical_badge = (
            fallback_classification["badge"]
        )

    if canonical_badge:
        result.setdefault(
            "institutional_badge",
            canonical_badge,
        )

        result.setdefault(
            "badge",
            canonical_badge,
        )

    if not result.get("signal_class"):
        if fallback_classification:
            result["signal_class"] = (
                fallback_classification[
                    "signal_class"
                ]
            )
        else:
            result["signal_class"] = (
                "watchlist"
            )

    result.setdefault(
        "institutional_reasons",
        _build_reasons(
            ai_score=ai_score,
            relative_volume=relative_volume,
            trend=trend,
            momentum=momentum,
            change_pct=change_pct,
            volume_rank=safe_volume_rank,
            volume=volume,
        ),
    )

    result.setdefault(
        "explanation",
        result.get(
            "institutional_reasons",
            [],
        ),
    )

    return result

