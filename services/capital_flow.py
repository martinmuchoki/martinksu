from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List

from services.sector_utils import normalize_sector


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


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
    return max(
        minimum,
        min(maximum, value),
    )


def _reliability_weight(
    reliability: Any,
) -> float:
    """
    Reduce the influence of stocks with limited historical data.
    """
    label = str(
        reliability or ""
    ).strip().upper()

    weights = {
        "HIGH": 1.00,
        "MEDIUM": 0.85,
        "LOW": 0.65,
        "LEGACY_BASELINE": 0.55,
        "INSUFFICIENT_HISTORY": 0.40,
    }

    return weights.get(label, 0.55)


def _liquidity_weight(
    liquidity_score: Any,
) -> float:
    """
    Convert the 0-100 liquidity score into a conservative weight.

    Even lower-liquidity stocks retain some influence, but liquid
    counters have greater impact on market-wide capital-flow analysis.
    """
    liquidity = _clamp(
        _safe_float(liquidity_score)
    )

    return 0.25 + (
        liquidity / 100.0
    ) * 0.75


def _volume_weight(
    relative_volume: Any,
) -> float:
    """
    Convert relative volume into a bounded activity weight.
    """
    rvol = max(
        0.0,
        _safe_float(relative_volume)
    )

    if rvol <= 0:
        return 0.35

    return _clamp(
        0.50 + min(rvol, 4.0) / 4.0,
        0.50,
        1.50,
    )


def _price_confirmation(
    change_pct: Any,
) -> Dict[str, float]:
    """
    Create positive and negative price confirmation values.
    """
    change = _safe_float(change_pct)

    positive = _clamp(
        50.0 + change * 10.0
    )

    negative = _clamp(
        50.0 - change * 10.0
    )

    return {
        "positive": positive,
        "negative": negative,
    }


def _stock_flow_profile(
    stock: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate one stock's contribution to market capital flow.

    This function consumes canonical institutional probabilities.
    It does not recalculate institutional classification.
    """
    symbol = str(
        stock.get("symbol") or ""
    ).strip().upper()

    accumulation_probability = _clamp(
        _safe_float(
            stock.get(
                "institutional_probability"
            )
        )
    )

    distribution_probability = _clamp(
        _safe_float(
            stock.get(
                "distribution_probability"
            )
        )
    )

    liquidity_score = _clamp(
        _safe_float(
            stock.get("liquidity_score")
        )
    )

    relative_volume = max(
        0.0,
        _safe_float(
            stock.get("relative_volume")
        ),
    )

    change_pct = _safe_float(
        stock.get(
            "change_pct",
            stock.get(
                "change_percent",
                0.0,
            ),
        )
    )

    reliability = str(
        stock.get(
            "statistics_reliability"
        ) or "LEGACY_BASELINE"
    ).strip().upper()

    price_confirmation = (
        _price_confirmation(change_pct)
    )

    reliability_weight = (
        _reliability_weight(reliability)
    )

    liquidity_weight = (
        _liquidity_weight(liquidity_score)
    )

    volume_weight = (
        _volume_weight(relative_volume)
    )

    combined_weight = (
        reliability_weight
        * liquidity_weight
        * volume_weight
    )

    buying_strength = (
        accumulation_probability * 0.70
        + price_confirmation["positive"]
        * 0.20
        + liquidity_score * 0.10
    )

    selling_strength = (
        distribution_probability * 0.70
        + price_confirmation["negative"]
        * 0.20
        + liquidity_score * 0.10
    )

    weighted_buying = (
        buying_strength
        * combined_weight
    )

    weighted_selling = (
        selling_strength
        * combined_weight
    )

    net_flow = (
        weighted_buying
        - weighted_selling
    )

    return {
        "symbol": symbol,
        "sector": normalize_sector(
            stock.get("sector")
            or stock.get("sector_name")
            or stock.get("market_sector")
            or stock.get("industry")
            or stock.get("category")
        ),
        "institutional_probability": round(
            accumulation_probability,
            2,
        ),
        "distribution_probability": round(
            distribution_probability,
            2,
        ),
        "liquidity_score": round(
            liquidity_score,
            2,
        ),
        "relative_volume": round(
            relative_volume,
            2,
        ),
        "change_pct": round(
            change_pct,
            2,
        ),
        "statistics_reliability": reliability,
        "reliability_weight": round(
            reliability_weight,
            4,
        ),
        "liquidity_weight": round(
            liquidity_weight,
            4,
        ),
        "volume_weight": round(
            volume_weight,
            4,
        ),
        "combined_weight": round(
            combined_weight,
            4,
        ),
        "buying_strength": round(
            buying_strength,
            2,
        ),
        "selling_strength": round(
            selling_strength,
            2,
        ),
        "weighted_buying": round(
            weighted_buying,
            4,
        ),
        "weighted_selling": round(
            weighted_selling,
            4,
        ),
        "net_flow": round(
            net_flow,
            4,
        ),
        "institutional_signal": stock.get(
            "institutional_signal"
        ),
        "signal_class": stock.get(
            "signal_class"
        ),
    }


def _market_bias(
    capital_flow_index: float,
    net_flow_score: float,
) -> Dict[str, str]:
    """
    Classify market-wide institutional flow.
    """
    if (
        capital_flow_index >= 68
        and net_flow_score >= 15
    ):
        return {
            "market_bias": (
                "Strong Institutional Accumulation"
            ),
            "market_bias_label": (
                "Strong Bullish"
            ),
            "market_bias_badge": "🔥",
            "market_bias_class": (
                "strong-accumulation"
            ),
        }

    if (
        capital_flow_index >= 56
        and net_flow_score >= 5
    ):
        return {
            "market_bias": (
                "Institutional Accumulation"
            ),
            "market_bias_label": "Bullish",
            "market_bias_badge": "🟢",
            "market_bias_class": (
                "accumulation"
            ),
        }

    if (
        capital_flow_index <= 32
        and net_flow_score <= -15
    ):
        return {
            "market_bias": (
                "Strong Institutional Distribution"
            ),
            "market_bias_label": (
                "Strong Bearish"
            ),
            "market_bias_badge": "🔴",
            "market_bias_class": (
                "strong-distribution"
            ),
        }

    if (
        capital_flow_index <= 44
        and net_flow_score <= -5
    ):
        return {
            "market_bias": (
                "Institutional Distribution"
            ),
            "market_bias_label": "Bearish",
            "market_bias_badge": "🟠",
            "market_bias_class": (
                "distribution"
            ),
        }

    return {
        "market_bias": (
            "Balanced Institutional Participation"
        ),
        "market_bias_label": "Neutral",
        "market_bias_badge": "⚪",
        "market_bias_class": "neutral",
    }


def calculate_market_capital_flow(
    stocks: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Aggregate canonical stock profiles into market-wide capital flow.

    Market Capital Flow Index:
        0   = maximum distribution pressure
        50  = balanced participation
        100 = maximum accumulation pressure
    """
    profiles: List[Dict[str, Any]] = []

    seen_symbols = set()

    for stock in stocks:
        if not isinstance(stock, dict):
            continue

        symbol = str(
            stock.get("symbol") or ""
        ).strip().upper()

        if not symbol:
            continue

        if symbol in seen_symbols:
            continue

        seen_symbols.add(symbol)

        institutional_probability = (
            stock.get(
                "institutional_probability"
            )
        )

        distribution_probability = (
            stock.get(
                "distribution_probability"
            )
        )

        if (
            institutional_probability is None
            or distribution_probability is None
        ):
            continue

        profile = _stock_flow_profile(
            stock
        )

        profiles.append(profile)

    if not profiles:
        neutral_bias = _market_bias(
            50.0,
            0.0,
        )

        return {
            "market_capital_flow_index": 50.0,
            "capital_flow_index": 50.0,
            "institutional_buying_score": 0.0,
            "institutional_selling_score": 0.0,
            "net_capital_flow_score": 0.0,
            "accumulation_count": 0,
            "distribution_count": 0,
            "neutral_count": 0,
            "active_stock_count": 0,
            "total_weight": 0.0,
            "accumulation_percentage": 0.0,
            "distribution_percentage": 0.0,
            "neutral_percentage": 0.0,
            "top_accumulation": [],
            "top_distribution": [],
            "stock_flow_profiles": [],
            **neutral_bias,
        }

    total_weight = sum(
        profile["combined_weight"]
        for profile in profiles
    )

    weighted_buying_total = sum(
        profile["weighted_buying"]
        for profile in profiles
    )

    weighted_selling_total = sum(
        profile["weighted_selling"]
        for profile in profiles
    )

    if total_weight > 0:
        buying_score = (
            weighted_buying_total
            / total_weight
        )

        selling_score = (
            weighted_selling_total
            / total_weight
        )
    else:
        buying_score = 0.0
        selling_score = 0.0

    net_flow_score = (
        buying_score
        - selling_score
    )

    capital_flow_index = _clamp(
        50.0 + net_flow_score
    )

    accumulation_profiles = [
        profile
        for profile in profiles
        if profile["net_flow"] >= 5.0
    ]

    distribution_profiles = [
        profile
        for profile in profiles
        if profile["net_flow"] <= -5.0
    ]

    neutral_profiles = [
        profile
        for profile in profiles
        if -5.0 < profile["net_flow"] < 5.0
    ]

    accumulation_profiles.sort(
        key=lambda item: (
            item["net_flow"],
            item["weighted_buying"],
        ),
        reverse=True,
    )

    distribution_profiles.sort(
        key=lambda item: (
            item["net_flow"],
            -item["weighted_selling"],
        ),
    )

    profile_count = len(profiles)

    bias = _market_bias(
        capital_flow_index,
        net_flow_score,
    )

    return {
        "market_capital_flow_index": round(
            capital_flow_index,
            2,
        ),
        "capital_flow_index": round(
            capital_flow_index,
            2,
        ),
        "institutional_buying_score": round(
            _clamp(buying_score),
            2,
        ),
        "institutional_selling_score": round(
            _clamp(selling_score),
            2,
        ),
        "net_capital_flow_score": round(
            net_flow_score,
            2,
        ),
        "accumulation_count": len(
            accumulation_profiles
        ),
        "distribution_count": len(
            distribution_profiles
        ),
        "neutral_count": len(
            neutral_profiles
        ),
        "active_stock_count": profile_count,
        "total_weight": round(
            total_weight,
            4,
        ),
        "accumulation_percentage": round(
            len(accumulation_profiles)
            / profile_count
            * 100.0,
            2,
        ),
        "distribution_percentage": round(
            len(distribution_profiles)
            / profile_count
            * 100.0,
            2,
        ),
        "neutral_percentage": round(
            len(neutral_profiles)
            / profile_count
            * 100.0,
            2,
        ),
        "top_accumulation": (
            accumulation_profiles[:10]
        ),
        "top_distribution": (
            distribution_profiles[:10]
        ),
        "stock_flow_profiles": profiles,
        **bias,
    }


def get_market_capital_flow(
    stocks: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Public compatibility alias.
    """
    return calculate_market_capital_flow(
        stocks
    )
