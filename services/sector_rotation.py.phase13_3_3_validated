"""
Institutional Sector Rotation Engine.

Consumes canonical Capital Flow stock profiles and produces
sector-level institutional rotation analytics.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, value))


def _normalize_net_flow(average_net_flow: float) -> float:
    return _clamp(50.0 + average_net_flow * 2.0)


def _rotation_phase(score: float) -> str:
    if score >= 80:
        return "Strong Accumulation"
    if score >= 65:
        return "Accumulation"
    if score >= 50:
        return "Improving"
    if score >= 40:
        return "Neutral"
    if score >= 25:
        return "Weakening"
    return "Distribution"


def _rotation_direction(score: float) -> str:
    if score >= 65:
        return "UP"
    if score < 40:
        return "DOWN"
    return "FLAT"


def _group_by_sector(
    stock_flow_profiles: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen_symbols = set()

    for profile in stock_flow_profiles:
        if not isinstance(profile, dict):
            continue

        symbol = str(profile.get("symbol") or "").strip().upper()

        if not symbol or symbol in seen_symbols:
            continue

        seen_symbols.add(symbol)

        sector = str(profile.get("sector") or "Other").strip() or "Other"
        grouped[sector].append(profile)

    return dict(grouped)



def _sector_confidence_score(stock_count: int) -> float:
    if stock_count >= 8:
        return 100.0
    if stock_count >= 5:
        return 80.0
    if stock_count >= 3:
        return 60.0
    if stock_count == 2:
        return 40.0
    if stock_count == 1:
        return 25.0
    return 0.0


def _sector_metrics(
    sector: str,
    profiles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stock_count = len(profiles)

    if stock_count == 0:
        raise ValueError(f"Sector {sector!r} contains no profiles")

    net_flows = [
        _safe_float(profile.get("net_flow"))
        for profile in profiles
    ]

    institutional_probabilities = [
        _safe_float(profile.get("institutional_probability"))
        for profile in profiles
    ]

    distribution_probabilities = [
        _safe_float(profile.get("distribution_probability"))
        for profile in profiles
    ]

    liquidity_scores = [
        _safe_float(
            profile.get("liquidity_score"),
            _safe_float(profile.get("liquidity"), 50.0),
        )
        for profile in profiles
    ]

    combined_weights = [
        max(
            0.0,
            _safe_float(profile.get("combined_weight"), 1.0),
        )
        for profile in profiles
    ]

    accumulation_count = sum(
        1 for value in net_flows if value >= 5.0
    )

    distribution_count = sum(
        1 for value in net_flows if value <= -5.0
    )

    neutral_count = (
        stock_count
        - accumulation_count
        - distribution_count
    )

    average_net_flow = sum(net_flows) / stock_count

    average_institutional_probability = (
        sum(institutional_probabilities) / stock_count
    )

    average_distribution_probability = (
        sum(distribution_probabilities) / stock_count
    )

    average_liquidity = sum(liquidity_scores) / stock_count

    total_weight = sum(combined_weights)

    if total_weight > 0:
        weighted_net_flow = (
            sum(
                net_flow * weight
                for net_flow, weight in zip(
                    net_flows,
                    combined_weights,
                )
            )
            / total_weight
        )
    else:
        weighted_net_flow = average_net_flow

    capital_flow_index = _clamp(
        50.0 + weighted_net_flow
    )

    normalized_net_flow = _normalize_net_flow(
        average_net_flow
    )

    raw_rotation_score = _clamp(
        capital_flow_index * 0.40
        + normalized_net_flow * 0.30
        + average_institutional_probability * 0.20
        + average_liquidity * 0.10
    )

    breadth_score = _clamp(
        accumulation_count / stock_count * 100.0
    )

    confidence_score = _sector_confidence_score(
        stock_count
    )

    reliable_breadth_score = _clamp(
        breadth_score
        * confidence_score
        / 100.0
    )

    adjusted_rotation_score = _clamp(
        raw_rotation_score * 0.75
        + reliable_breadth_score * 0.15
        + confidence_score * 0.10
    )

    strongest_profile = max(
        profiles,
        key=lambda item: (
            _safe_float(item.get("net_flow")),
            _safe_float(
                item.get("institutional_probability")
            ),
        ),
    )

    weakest_profile = min(
        profiles,
        key=lambda item: (
            _safe_float(item.get("net_flow")),
            -_safe_float(
                item.get("distribution_probability")
            ),
        ),
    )

    return {
        "sector": sector,
        "stock_count": stock_count,
        "accumulation_count": accumulation_count,
        "distribution_count": distribution_count,
        "neutral_count": neutral_count,
        "accumulation_percentage": round(
            accumulation_count / stock_count * 100.0,
            2,
        ),
        "distribution_percentage": round(
            distribution_count / stock_count * 100.0,
            2,
        ),
        "average_net_flow": round(average_net_flow, 4),
        "weighted_net_flow": round(weighted_net_flow, 4),
        "average_institutional_probability": round(
            average_institutional_probability,
            2,
        ),
        "average_distribution_probability": round(
            average_distribution_probability,
            2,
        ),
        "average_liquidity": round(average_liquidity, 2),
        "capital_flow_index": round(capital_flow_index, 2),
        "raw_rotation_score": round(raw_rotation_score, 2),
        "breadth_score": round(breadth_score, 2),
        "confidence_score": round(confidence_score, 2),
        "reliable_breadth_score": round(
            reliable_breadth_score,
            2,
        ),
        "adjusted_rotation_score": round(
            adjusted_rotation_score,
            2,
        ),
        "rotation_score": round(
            adjusted_rotation_score,
            2,
        ),
        "rotation_phase": _rotation_phase(
            adjusted_rotation_score
        ),
        "rotation_direction": _rotation_direction(
            adjusted_rotation_score
        ),
        "top_stock": dict(strongest_profile),
        "weakest_stock": dict(weakest_profile),
    }


def get_sector_rotation(
    stock_flow_profiles: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    grouped = _group_by_sector(stock_flow_profiles)

    rankings = [
        _sector_metrics(sector, profiles)
        for sector, profiles in grouped.items()
    ]

    rankings.sort(
        key=lambda item: (
            item["adjusted_rotation_score"],
            item["raw_rotation_score"],
            item["capital_flow_index"],
        ),
        reverse=True,
    )

    for rank, item in enumerate(rankings, start=1):
        item["rank"] = rank

    sector_count = len(rankings)

    stock_count = sum(
        item["stock_count"]
        for item in rankings
    )

    if sector_count:
        market_rotation_strength = (
            sum(
                item["adjusted_rotation_score"]
                for item in rankings
            )
            / sector_count
        )
    else:
        market_rotation_strength = 50.0

    phases = (
        "Strong Accumulation",
        "Accumulation",
        "Improving",
        "Neutral",
        "Weakening",
        "Distribution",
    )

    summary = {
        phase.lower().replace(" ", "_"): sum(
            item["rotation_phase"] == phase
            for item in rankings
        )
        for phase in phases
    }

    return {
        "market_rotation_strength": round(
            market_rotation_strength,
            2,
        ),
        "rotation_phase": _rotation_phase(
            market_rotation_strength
        ),
        "sector_count": sector_count,
        "stock_count": stock_count,
        "leaders": rankings[:5],
        "laggards": sorted(
            rankings,
            key=lambda item: (
                item["adjusted_rotation_score"],
                item["raw_rotation_score"],
            ),
        )[:5],
        "sector_rankings": rankings,
        "summary": summary,
    }


def calculate_sector_rotation(
    stock_flow_profiles: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    return get_sector_rotation(stock_flow_profiles)
