from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from services.prediction_center import build_prediction_center


KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
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


def _decision_from_score(score: float) -> str:
    if score >= 88:
        return "STRONG BUY"
    if score >= 74:
        return "BUY"
    if score >= 58:
        return "HOLD"
    if score >= 44:
        return "WATCH"
    return "AVOID"


def _technical_vote(profile: Dict[str, Any]) -> Dict[str, Any]:
    score = 50.0
    trend = str(profile.get("trend") or "").upper()
    rsi = _safe_float(profile.get("rsi"), 50.0)
    macd = _safe_float(profile.get("macd"), 0.0)
    reasons: List[str] = []

    if "UPTREND" in trend or "BULL" in trend:
        score += 24
        reasons.append("Bullish technical trend")
    elif "DOWNTREND" in trend or "BEAR" in trend:
        score -= 24
        reasons.append("Bearish technical trend")

    if 50 <= rsi <= 68:
        score += 14
        reasons.append("RSI supports positive momentum")
    elif rsi >= 75:
        score -= 8
        reasons.append("RSI indicates overbought conditions")
    elif rsi <= 35:
        score -= 10
        reasons.append("RSI indicates weak momentum")

    if macd > 0:
        score += 12
        reasons.append("Positive MACD")
    elif macd < 0:
        score -= 12
        reasons.append("Negative MACD")

    score = _clamp(score)

    return {
        "name": "Technical Analyst",
        "role": "Technical Analysis",
        "score": round(score, 2),
        "decision": _decision_from_score(score),
        "confidence": _safe_int(score),
        "reasons": reasons[:3],
    }


def _quant_vote(profile: Dict[str, Any]) -> Dict[str, Any]:
    conviction = _safe_float(
        profile.get("conviction_score"),
        50.0,
    )
    probability = _safe_float(
        profile.get("prediction_probability_pct"),
        50.0,
    )
    expected_return = _safe_float(
        profile.get("expected_return"),
        0.0,
    )

    return_component = _clamp(
        50.0 + expected_return * 2.5
    )

    score = (
        conviction * 0.50
        + probability * 0.30
        + return_component * 0.20
    )

    return {
        "name": "Quantitative Analyst",
        "role": "Predictive Intelligence",
        "score": round(score, 2),
        "decision": _decision_from_score(score),
        "confidence": _safe_int(score),
        "reasons": [
            f"Conviction score {conviction:.0f}",
            f"Prediction probability {probability:.1f}%",
            f"Expected return {expected_return:+.2f}%",
        ],
    }


def _institutional_vote(
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    confidence = _safe_float(
        profile.get("institutional_confidence"),
        50.0,
    )
    signal = str(
        profile.get("institutional_signal") or ""
    ).upper()
    rvol = _safe_float(
        profile.get("relative_volume"),
        0.0,
    )

    score = confidence
    reasons: List[str] = []

    if any(
        term in signal
        for term in (
            "BUYING",
            "ACCUMULATION",
            "BREAKOUT",
        )
    ):
        score += 12
        reasons.append(
            profile.get("institutional_signal")
            or "Institutional accumulation"
        )
    elif any(
        term in signal
        for term in (
            "DISTRIBUTION",
            "SELLING",
        )
    ):
        score -= 18
        reasons.append(
            "Institutional distribution detected"
        )

    if rvol >= 5:
        score += 10
        reasons.append(
            f"High relative volume {rvol:.2f}×"
        )
    elif rvol >= 1.5:
        score += 5
        reasons.append(
            f"Above-average participation {rvol:.2f}×"
        )

    score = _clamp(score)

    return {
        "name": "Institutional Flow Analyst",
        "role": "Institutional Intelligence",
        "score": round(score, 2),
        "decision": _decision_from_score(score),
        "confidence": _safe_int(score),
        "reasons": reasons[:3],
    }


def _risk_vote(profile: Dict[str, Any]) -> Dict[str, Any]:
    risk = str(
        profile.get("risk_level")
        or "INSUFFICIENT HISTORY"
    ).upper()

    volatility = abs(
        _safe_float(
            profile.get("volatility_pct"),
            0.0,
        )
    )
    drawdown = abs(
        _safe_float(
            profile.get("maximum_drawdown_pct"),
            0.0,
        )
    )
    sharpe = _safe_float(
        profile.get("sharpe_ratio"),
        0.0,
    )

    score = {
        "LOW": 82.0,
        "MEDIUM": 65.0,
        "HIGH": 40.0,
        "INSUFFICIENT HISTORY": 48.0,
    }.get(risk, 50.0)

    reasons = [f"Risk level {risk}"]

    if sharpe >= 2:
        score += 10
        reasons.append(
            f"Strong Sharpe ratio {sharpe:.2f}"
        )
    elif sharpe < 0:
        score -= 10
        reasons.append(
            f"Negative Sharpe ratio {sharpe:.2f}"
        )

    if volatility >= 60:
        score -= 10
        reasons.append(
            f"High volatility {volatility:.2f}%"
        )

    if drawdown >= 25:
        score -= 10
        reasons.append(
            f"Large drawdown {drawdown:.2f}%"
        )

    score = _clamp(score)

    return {
        "name": "Risk Manager",
        "role": "Risk Control",
        "score": round(score, 2),
        "decision": _decision_from_score(score),
        "confidence": _safe_int(score),
        "reasons": reasons[:3],
    }


def _learning_vote(
    profile: Dict[str, Any],
    learning: Dict[str, Any],
) -> Dict[str, Any]:
    accuracy = _safe_float(
        learning.get("accuracy"),
        profile.get("learning_accuracy", 50.0),
    )
    learning_score = _safe_float(
        learning.get("learning_score"),
        50.0,
    )
    adjustment = _safe_float(
        learning.get("confidence_adjustment"),
        0.0,
    )

    score = _clamp(
        accuracy * 0.60
        + learning_score * 0.40
        + adjustment
    )

    return {
        "name": "Learning AI",
        "role": "Adaptive Intelligence",
        "score": round(score, 2),
        "decision": _decision_from_score(score),
        "confidence": _safe_int(score),
        "reasons": [
            f"Historical accuracy {accuracy:.2f}%",
            f"Learning score {learning_score:.2f}%",
            f"Adaptive adjustment {adjustment:+.2f}",
        ],
    }


def build_committee_decision(
    profile: Dict[str, Any],
    learning: Dict[str, Any],
    market_regime: Dict[str, Any],
) -> Dict[str, Any]:
    agents = [
        _technical_vote(profile),
        _quant_vote(profile),
        _institutional_vote(profile),
        _risk_vote(profile),
        _learning_vote(profile, learning),
    ]

    weights = {
        "Technical Analysis": 0.22,
        "Predictive Intelligence": 0.28,
        "Institutional Intelligence": 0.20,
        "Risk Control": 0.20,
        "Adaptive Intelligence": 0.10,
    }

    weighted_score = sum(
        agent["score"]
        * weights.get(agent["role"], 0.0)
        for agent in agents
    )

    regime_multiplier = _safe_float(
        market_regime.get("conviction_multiplier"),
        1.0,
    )

    final_score = _clamp(
        weighted_score * regime_multiplier
    )

    final_decision = _decision_from_score(
        final_score
    )

    votes = Counter(
        agent["decision"]
        for agent in agents
    )

    consensus_count = votes.most_common(1)[0][1]
    consensus_pct = round(
        consensus_count / len(agents) * 100,
        2,
    )

    reasons: List[str] = []
    for agent in agents:
        for reason in agent["reasons"]:
            if reason not in reasons:
                reasons.append(reason)

    return {
        "symbol": profile.get("symbol"),
        "name": profile.get("name"),
        "price": profile.get("price"),
        "final_decision": final_decision,
        "committee_score": round(
            final_score,
            2,
        ),
        "confidence": _safe_int(
            final_score * 0.70
            + consensus_pct * 0.30
        ),
        "consensus_pct": consensus_pct,
        "vote_distribution": dict(votes),
        "market_regime":
            market_regime.get("regime"),
        "market_regime_badge":
            market_regime.get("badge"),
        "conviction_score":
            profile.get("conviction_score"),
        "expected_return":
            profile.get("expected_return"),
        "target_price":
            profile.get("target_price"),
        "risk_level":
            profile.get("risk_level"),
        "institutional_signal":
            profile.get("institutional_signal"),
        "agents": agents,
        "reasons": reasons[:8],
    }


def build_ai_investment_committee() -> Dict[str, Any]:
    prediction_center = build_prediction_center()

    profiles = prediction_center.get(
        "predictions",
        [],
    )
    learning = prediction_center.get(
        "learning",
        {},
    )
    market_regime = prediction_center.get(
        "market_regime",
        {},
    )

    decisions = [
        build_committee_decision(
            profile=profile,
            learning=learning,
            market_regime=market_regime,
        )
        for profile in profiles
    ]

    decisions.sort(
        key=lambda item: (
            item["committee_score"],
            item["confidence"],
        ),
        reverse=True,
    )

    decision_counts = Counter(
        item["final_decision"]
        for item in decisions
    )

    return {
        "version":
            "11.7 AI Investment Committee",
        "generated_at": datetime.now(
            KENYA_TIMEZONE
        ).isoformat(),
        "market_regime": market_regime,
        "decision_count": len(decisions),
        "summary": {
            "strong_buy_count":
                decision_counts.get(
                    "STRONG BUY",
                    0,
                ),
            "buy_count":
                decision_counts.get(
                    "BUY",
                    0,
                ),
            "hold_count":
                decision_counts.get(
                    "HOLD",
                    0,
                ),
            "watch_count":
                decision_counts.get(
                    "WATCH",
                    0,
                ),
            "avoid_count":
                decision_counts.get(
                    "AVOID",
                    0,
                ),
            "top_symbol":
                decisions[0]["symbol"]
                if decisions
                else None,
            "top_score":
                decisions[0]["committee_score"]
                if decisions
                else 0,
        },
        "decisions": decisions,
    }
